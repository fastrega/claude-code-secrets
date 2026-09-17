"""
OpenRouter fan-out.

One API key reaches Anthropic, OpenAI, Google, xAI, DeepSeek, Qwen, Moonshot and
the rest behind a single OpenAI-compatible endpoint, which is what makes a
multi-model consensus practical to run every week.

Model slugs move as providers ship new versions, so nothing is hardcoded here —
the roster lives in `config/models.json` and `list_models()` tells you what your
key can actually reach right now.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

BASE = "https://openrouter.ai/api/v1"
CONFIG = Path(__file__).resolve().parents[2] / "config" / "models.json"

RETRIES = 4
BACKOFF = [2, 6, 15, 40]


class OpenRouterError(RuntimeError):
    pass


# Searched in order. The first file that defines the key wins, and a real
# environment variable beats all of them. Nothing here is ever committed:
# `.env` is gitignored and the config path lives outside the repo entirely.
ENV_FILES = [
    Path(__file__).resolve().parents[2] / ".env",
    Path.home() / ".config" / "atsc" / "env",
]


def _load_env_files() -> None:
    """
    Minimal dotenv reader — no dependency, no surprises.

    Only fills variables that are not already set, so an explicitly exported
    value always wins over a file. Values are not expanded or interpreted: a key
    is an opaque string and shell-style expansion of one is a good way to
    silently mangle it.
    """
    for path in ENV_FILES:
        try:
            if not path.is_file():
                continue
            for raw in path.read_text().splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                name = name.strip().removeprefix("export ").strip()
                value = value.strip().strip('"').strip("'")
                if name and value and name not in os.environ:
                    os.environ[name] = value
        except OSError:
            continue


def key_source() -> str | None:
    """Where the key came from, for diagnostics. Never returns the key itself."""
    if os.environ.get("OPENROUTER_API_KEY"):
        return "environment"
    for path in ENV_FILES:
        try:
            if path.is_file() and "OPENROUTER_API_KEY" in path.read_text():
                return str(path)
        except OSError:
            continue
    return None


def _key() -> str:
    k = os.environ.get("OPENROUTER_API_KEY")
    if not k:
        _load_env_files()
        k = os.environ.get("OPENROUTER_API_KEY")
    if not k:
        raise OpenRouterError(
            "OPENROUTER_API_KEY is not set. Put it in one of:\n"
            f"  {ENV_FILES[0]}          (per-repo; gitignored)\n"
            f"  {ENV_FILES[1]}   (all repos; outside git entirely)\n"
            "as a single line:  OPENROUTER_API_KEY=sk-or-v1-...\n"
            "Or export it for one shell. For GitHub Actions use a repository secret.\n"
            "Get a key at https://openrouter.ai/keys — one covers the whole field."
        )
    if k.startswith("sk-or-v1-REPLACE") or k == "sk-or-v1-...":
        raise OpenRouterError(
            f"OPENROUTER_API_KEY is still the placeholder from .env.example "
            f"(source: {key_source()}). Replace it with your real key."
        )
    return k


def _request(path: str, payload: dict | None = None, timeout: int = 900) -> dict:
    url = f"{BASE}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Authorization", f"Bearer {_key()}")
    req.add_header("Content-Type", "application/json")
    # OpenRouter uses these for attribution on its dashboard.
    req.add_header("HTTP-Referer", "https://github.com/fastrega/claude-code-secrets")
    req.add_header("X-Title", "atsc NFL ATS consensus")

    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:400]
            # 429 and 5xx are worth retrying; a 400 or 401 will never succeed.
            if e.code in (408, 409, 429, 500, 502, 503, 504) and attempt < RETRIES - 1:
                last = e
                time.sleep(BACKOFF[attempt])
                continue
            raise OpenRouterError(f"HTTP {e.code} from {path}: {body}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < RETRIES - 1:
                last = e
                time.sleep(BACKOFF[attempt])
                continue
            raise OpenRouterError(f"network failure calling {path}: {e}") from e
    raise OpenRouterError(f"exhausted retries calling {path}: {last}")


def list_models(search: str | None = None) -> list[dict]:
    """Everything the key can reach, optionally filtered. Slugs change; check here."""
    data = _request("/models", None, timeout=90)
    rows = data.get("data", [])
    if search:
        s = search.lower()
        rows = [m for m in rows if s in m.get("id", "").lower() or s in m.get("name", "").lower()]
    return sorted(rows, key=lambda m: m.get("id", ""))


def load_roster(only: list[str] | None = None, include_disabled: bool = False) -> list[dict]:
    cfg = json.loads(CONFIG.read_text())
    models = cfg["models"]
    if not include_disabled:
        models = [m for m in models if m.get("enabled", True)]
    if only:
        wanted = {o.lower() for o in only}
        models = [m for m in models if m["name"].lower() in wanted]
    return models


def extract_json(text: str) -> dict:
    """
    Pull the JSON object out of a reply.

    Models wrap JSON in prose and fences no matter how firmly you ask them not to,
    and a reasoning model may emit a chain of thought first. Try the clean paths,
    then fall back to brace matching from the last plausible opening brace.
    """
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    for block in reversed(fenced):
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue

    # Brace matching, preferring the largest well-formed object.
    starts = [i for i, c in enumerate(text) if c == "{"]
    for start in starts:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError("no parseable JSON object in the reply")


def ask(model: dict, prompt: str, *, max_tokens: int = 16000,
        temperature: float = 0.3, archive: Path | None = None) -> tuple[dict, dict]:
    """
    Send one prompt to one model. Returns (parsed_json, metadata).

    When `archive` is given, the untouched response text is written there before
    parsing. Parsing is lossy — a model's caveats, its reasoning preamble, and
    anything it said outside the JSON all disappear. Keeping the raw text means
    the record is what the model actually said, not what the parser kept.
    """
    payload: dict[str, Any] = {
        "model": model["slug"],
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    effort = model.get("reasoning")
    if effort in ("low", "medium", "high"):
        payload["reasoning"] = {"effort": effort}

    t0 = time.time()
    resp = _request("/chat/completions", payload)
    choice = (resp.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content") or ""

    if archive:
        archive.parent.mkdir(parents=True, exist_ok=True)
        # Some providers return the reasoning trace separately from the answer.
        trace = message.get("reasoning") or message.get("reasoning_content") or ""
        archive.write_text(
            f"<!-- model: {model['name']} | slug: {model['slug']} | "
            f"finish: {choice.get('finish_reason')} -->\n\n"
            + (f"## Reasoning trace\n\n{trace}\n\n## Response\n\n" if trace else "")
            + content)

    parsed = extract_json(content)
    parsed.setdefault("model", model["name"])
    # The roster name is the identity the rest of the pipeline keys on; a model
    # naming itself something else would fragment its own results across weeks.
    parsed["model"] = model["name"]

    meta = {
        "slug": model["slug"],
        "seconds": round(time.time() - t0, 1),
        "finish_reason": choice.get("finish_reason"),
        "usage": resp.get("usage", {}),
        "raw_chars": len(content),
    }
    return parsed, meta


def fan_out(models: list[dict], prompt: str | Callable[[dict], str], out_dir: Path, *,
            max_workers: int = 4, suffix: str = "",
            on_event: Callable[[str], None] = print) -> dict[str, Any]:
    """
    Ask every API-lane model in parallel; write one JSON file each.

    One model failing never blocks the rest — a partial field is still a usable
    consensus, and the missing model can be added later by hand. Every raw reply
    is archived under `raw/` first, so a parse failure costs you the automation,
    not the answer.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    api = [m for m in models if m.get("lane") == "openrouter"]
    manual = [m for m in models if m.get("lane") != "openrouter"]
    # A callable lets each model get its own game ordering, which is how positional
    # bias is kept from correlating across the field.
    prompt_for = prompt if callable(prompt) else (lambda _m: prompt)

    results: dict[str, Any] = {"ok": [], "failed": [], "manual": [m["name"] for m in manual]}

    if manual:
        pending = out_dir / "MANUAL_LANE.md"
        pending.write_text(
            "# Manual lane\n\n"
            "These models have no general API. Paste the prompt pack into each, then save\n"
            f"the JSON reply into this directory as `<name>{suffix}.json`.\n\n"
            + "\n".join(f"- **{m['name']}** — {m.get('note', '')}" for m in manual) + "\n")
        on_event(f"  manual lane: {', '.join(m['name'] for m in manual)} "
                 f"(see {pending.name})")

    if not api:
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(ask, m, prompt_for(m),
                        archive=out_dir / "raw" / f"{m['name']}{suffix}.md"): m
            for m in api
        }
        for fut in as_completed(futures):
            m = futures[fut]
            try:
                parsed, meta = fut.result()
            except Exception as e:
                raw = out_dir / "raw" / f"{m['name']}{suffix}.md"
                hint = f" (raw reply saved to {raw.name})" if raw.exists() else ""
                on_event(f"  FAILED  {m['name']:<10} {type(e).__name__}: {e}{hint}")
                results["failed"].append({"model": m["name"], "error": str(e),
                                          "raw_saved": raw.exists()})
                continue

            parsed["_meta"] = meta
            path = out_dir / f"{m['name']}{suffix}.json"
            path.write_text(json.dumps(parsed, indent=2) + "\n")
            n = len(parsed.get("picks", []))
            on_event(f"  ok      {m['name']:<10} {meta['seconds']:>6.1f}s  "
                     f"{n} picks  {meta['usage'].get('total_tokens', '?')} tokens")
            results["ok"].append({"model": m["name"], "picks": n, "meta": meta})

    return results

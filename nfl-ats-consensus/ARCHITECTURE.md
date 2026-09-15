# Automation architecture

How to get from "paste a prompt into six chat windows" to "it runs itself on
Tuesday, Thursday and Sunday and emails me the card."

## The core constraint that shapes everything

The models you want in this consensus do not all have the same access story, and
the ones with the best reasoning modes are often the *hardest* to automate. Any
design that insists on full automation for all six will end up excluding the
models you most want.

So the pipeline is built around an **adapter interface**, not around any one API:

```
prompt pack  ──►  adapter  ──►  data/picks/<model>.json
                    │
                    ├── api        fully automated (key + HTTP)
                    ├── browser    scripted paste (Playwright), semi-automated
                    └── manual     you paste, you save the reply
```

Every adapter produces the same artifact: one JSON file per model per week. The
battle, adjudication and grading stages never know or care which adapter produced
a file. That means you can start 100% manual on week 1, automate two models on
week 3, and never change the rest of the system.

## Tier the models by how automatable they are

| Model | Route | Deep-research mode | Automation tier |
|---|---|---|---|
| Claude | Anthropic API | extended thinking, exposed as a request parameter | **api** — fully automated |
| ChatGPT / GPT | OpenAI API | reasoning-effort parameter on reasoning models | **api** — fully automated |
| Gemini | Google AI Studio API | thinking budget parameter | **api** — fully automated |
| Grok | xAI API | reasoning parameter | **api** — fully automated |
| DeepSeek / Qwen / Kimi / GLM | Own APIs, or OpenRouter | reasoner variants | **api** — cheapest tier by far |
| Manus | Agent product, no general API | its own agentic research | **manual or browser** |
| ChatGPT *Deep Research* (the product feature) | Not the same as the API | long-running, cited | **manual** — worth it for Round 2 only |

Two things worth knowing before you build:

1. **The API and the chat product are not the same model behaviour.** "ChatGPT Deep
   Research" and "Gemini Deep Research" are agentic products that browse and cite.
   The APIs give you the underlying reasoning model, which is excellent but does not
   browse the same way. For Round 1 the API is the right call — the dossier already
   contains the research. For Round 2, the browsing products genuinely add value,
   which is the argument for keeping a manual lane open.
2. **OpenRouter collapses five keys into one.** It fronts Anthropic, OpenAI, Google,
   xAI, DeepSeek, Qwen and others behind a single OpenAI-compatible endpoint. For a
   fan-out harness this removes most of the integration work. The trade-off is that
   provider-specific reasoning parameters are exposed unevenly, so for the models
   where deep thinking matters most you may still want the native SDK.

**Recommended split:** OpenRouter for the breadth (five to seven models, one key),
native Anthropic/OpenAI/Google SDKs for the two or three you care most about and
want full reasoning control over, manual for Manus.

## Why the pipeline is file-based

Every stage reads and writes plain files in `data/`. This is not laziness — it buys
three things that matter here:

- **A manual lane that costs nothing.** A model with no API is a file you save by
  hand. Nothing else changes.
- **A permanent audit trail.** Commit `data/` to git and you have every line, every
  pick, every rebuttal and every grade, immutable and diffable. When a model claims
  it said something different, the commit history settles it.
- **Resumability.** Three of six models answered before you hit a rate limit? Run
  `battle` on three, add the rest later. Nothing is transactional.

## Scheduling

Three runs a week, matching how information actually arrives:

- **Tuesday, shortly after CBS posts** — lock the line, build dossiers, fan out
  Round 1, run the battle, adjudicate. This is the big run.
- **Thursday morning** — rebuild dossiers only. Wednesday practice reports are in,
  the first real injury designations exist, TNF weather is firm. Re-poll the models
  on the Thursday game alone. The line does not move.
- **Saturday night or Sunday morning** — rebuild again. Final injury designations
  (they post Friday), final weather. Re-poll on any game where a designation
  actually changed — not the whole slate, or you burn budget re-asking questions
  whose inputs did not change.

The "only re-poll what changed" rule matters. Diff the new dossier against the
locked one; if a game's injury and weather sections are byte-identical, there is
nothing to re-ask.

### Where to run it

**GitHub Actions** is the right default: cron is built in, secrets management is
built in, the artifacts commit themselves back to the repo, and it is free for a
private repo at this volume. A workflow skeleton is in `.github/workflows/`.

The one real limitation is that Actions cron is best-effort and can be delayed by
several minutes under load — irrelevant here, since nothing in this pipeline is
time-critical to the minute.

A local cron job or a small always-on box works equally well and avoids putting
API keys in a cloud runner. Choose based on whether you want the git history in
the cloud.

## Cost

Round 1 is roughly 40-50k tokens of input per model (sixteen dossiers) and a
small output. Round 2 is much smaller — only contested games, only the models on
them. A six-model week is a few dollars at frontier pricing and cents if you lean
on the open-weight Chinese models for part of the field.

Two ways to cut it materially:

- **Prompt caching.** The dossier block is identical across all models from the same
  provider and identical across the Thursday and Sunday re-polls. Cache it.
- **Tier the field.** Run all six on Round 1, but only the top three by trailing
  calibration score through Round 2. A model with an inverted confidence signal
  is not worth paying to argue.

## What makes the consensus actually worth something

This is the part most multi-model setups get wrong, so it is worth stating plainly.

**Averaging model outputs does not work.** LLMs fail in correlated ways: they all
over-weight recent results, they all like the team with the famous quarterback,
they all under-weight opponent adjustment in September. Five models agreeing is
frequently one bias counted five times. That is why `battle` flags
`fragile_consensus` — unanimity where every model gave substantially the same reason
— and why the adjudicator is instructed to treat it as one argument rather than five.

**The disagreements are the product.** A game where the field splits 3-3 with high
stars on both sides is one where the evidence genuinely supports two readings. That
is worth more than a game where everyone agrees, and it is the only place the
rebuttal round earns its cost.

**Calibration beats record.** In the end-to-end test on Week 1, the model with the
best raw record (8-7-1) finished third by weighted score, because its confident
picks lost and its leans won. Over a season that is the difference between a system
that makes money and one that does not, and the raw record hides it completely.

## Build order

1. **Weeks 1-2: run it fully manual.** Six paste operations, six saved files. You
   will learn more about what the dossier is missing in two manual weeks than in a
   month of building adapters.
2. **Week 3: add the API adapter** for whichever models you have keys for. Keep the
   manual lane.
3. **Week 4: schedule it.** Tuesday/Thursday/Sunday, output to wherever you actually
   read things.
4. **Ongoing: feed grading back into the prompt.** Once you have four or five weeks
   of post-mortems, include each model's own trailing calibration verdict in its
   Round 1 prompt. A model told "your 4-star picks are 2-9 this season" adjusts. This
   is the compounding part of the system and it only works if you have been storing
   the grades from the start — which is why grading exists before automation does.

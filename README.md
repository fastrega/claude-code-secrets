# Claude Code Secrets

> Every hidden feature, internal codename, slash command, keyboard shortcut, environment variable, and feature flag found in the Claude Code source code.

**The source code ships with the npm package. They just didn't expect anyone to actually read all of it.**

---

## The 10 Craziest Things Buried in the Source Code

### 1. There's a Full Tamagotchi Pet System

Claude Code has an entire virtual pet companion hidden behind the `BUDDY` feature flag.

- **18 species**: Pebblecrab, Dustbunny, Mossfrog, Twigling, Dewdrop, Puddlefish, Cloudferret, Gustowl, Bramblebear, Thornfox, Crystaldrake, Deepstag, Lavapup, Stormwyrm, Voidcat, Aetherling, Cosmoshale, Nebulynx
- **Rarity tiers**: Common (60%) > Uncommon (25%) > Rare (10%) > Epic (4%) > Legendary (1%)
- **1% shiny variant** (independent of rarity)
- **5 procedural stats**: DEBUGGING, PATIENCE, CHAOS, WISDOM, SNARK (0-100 each)
- Claude writes a unique AI-generated "soul" personality for each pet at first hatch
- Uses Mulberry32 PRNG for deterministic per-user species generation

### 2. Claude Literally Dreams While You Sleep

A system called **autoDream** runs a background subagent that consolidates your memory files when you're idle.

- **Three-gate trigger**: 24 hours since last dream + at least 5 sessions + must acquire a consolidation lock
- **Four phases**: Orient → Gather Recent Signal → Consolidate → Prune and Index
- The prompt literally says: **"You are performing a dream"**
- Keeps your MEMORY.md under 200 lines and ~25KB
- The dream subagent gets read-only bash access
- GrowthBook gate: `tengu_onyx_plover`

### 3. ULTRAPLAN — 30-Minute Cloud Thinking Sessions

Offloads complex planning to a remote Cloud Container Runtime (CCR) session running **Opus 4.6** for up to **30 minutes**.

- Browser-based approval UI for watching and approving the plan in real-time
- 3-second polling for results
- Teleports the result back to your terminal via a sentinel called `__ULTRAPLAN_TELEPORT_LOCAL__`
- Feature flag: `ULTRAPLAN`

### 4. Undercover Mode — Hiding AI From Open Source

When Anthropic employees use Claude Code on open-source repos, it **automatically scrubs all evidence that an AI wrote the code**.

**What it blocks:**
- Internal model codenames (animal names like Capybara, Tengu)
- Unreleased model versions (opus-4-7, sonnet-4-8, etc.)
- Internal repo and project names
- Internal Slack channels and short links
- The phrase "Claude Code" or any mention of being AI
- Co-Authored-By attribution lines

Automatically active unless the repo remote matches an internal allowlist. Override with `CLAUDE_CODE_UNDERCOVER=1`. **There is no way to force it off.**

### 5. KAIROS — Always-On Persistent Assistant

An always-on assistant that watches and **proactively acts without user input**.

- Maintains append-only daily log files
- 15-second blocking budget for proactive actions
- "Brief" output mode — extremely concise responses
- Exclusive tools: `SendUserFile`, `PushNotification`, `SubscribePR`
- Feature flags: `KAIROS` / `PROACTIVE`
- Scheduled via background tick prompts

### 6. Coordinator Mode — AI Agent Swarms

One Claude becomes a swarm coordinator that spawns parallel worker agents.

- **Four phases**: Research → Synthesis → Implementation → Verification
- Shared scratchpad directory (gated behind `tengu_scratch`)
- Agent Swarm capabilities via `tengu_amber_flint` feature gate
- **In-process teammates** via `AsyncLocalStorage` context isolation
- **Process-based teammates** via tmux/iTerm2 panes
- Color assignments for visual distinction between agents

### 7. AFK Mode — Walk Away, Claude Keeps Building

Leave Claude running unsupervised. An ML transcript classifier auto-approves tool calls based on risk assessment.

- Risk classification: LOW, MEDIUM, HIGH
- Internal name for the classifier: **"YOLO classifier"**
- Beta header: `afk-mode-2026-01-31`
- Feature flag: `TRANSCRIPT_CLASSIFIER`

### 8. Computer Use (Codename: "Chicago")

Full desktop and browser control built on `@ant/computer-use-mcp`.

- Screenshot capture
- Mouse click and keyboard input
- Coordinate transformation
- Gated to Max/Pro subscriptions (bypassed for `USER_TYPE === 'ant'`)

### 9. Penguin Mode

Fast mode's **actual internal codename** is "Penguin Mode."

- API endpoint: `/api/claude_code_penguin_mode`
- Config key: `penguinModeOrgEnabled`
- Kill switch: `tengu_penguins_off`
- Analytics event: `tengu_org_penguin_mode_fetch_failed`

### 10. Voice Mode

Hold spacebar for push-to-talk voice input directly in the terminal.

- Feature flag: `VOICE_MODE`
- Streaming voice URL configurable via `VOICE_STREAM_BASE_URL`

---

## 900+ Internal Codenames

Every major system has an animal or geological codename:

| Codename | What It Actually Is |
|----------|-------------------|
| **Tengu** | Claude Code (the entire project) |
| **Fennec** | Opus model |
| **Capybara** | Internal model variant |
| **Chicago** | Computer Use feature |
| **Penguin Mode** | Fast mode |
| **Kairos** | Always-on assistant |
| **Lodestone** | Deep link system |
| **Onyx Plover** | autoDream configuration |
| **Amber Flint** | Agent swarm/teams system |
| **Willow** | Optimization mode |

There are **903 telemetry events** in the codebase, all prefixed with `tengu_`.

---

## 120+ Hidden Slash Commands

### Core
| Command | Aliases | What It Does |
|---------|---------|-------------|
| `/help` | | Show all commands |
| `/clear` | `/reset`, `/new` | Clear conversation history |
| `/compact` | | Clear history but keep a summary |
| `/exit` | `/quit` | Exit |
| `/version` | | Show version |
| `/status` | | Version, model, account, API, tools |
| `/doctor` | | Diagnose installation |
| `/cost` | | Session cost + duration |
| `/usage` | | Plan usage limits |
| `/stats` | | Usage statistics and activity |
| `/upgrade` | | Upgrade to Max plan |
| `/login` | | Sign in / switch accounts |
| `/logout` | | Sign out |
| `/feedback` | `/bug` | Submit feedback |
| `/release-notes` | | View release notes |

### Workflow & Git
| Command | Aliases | What It Does |
|---------|---------|-------------|
| `/commit` | | Create a git commit |
| `/commit-push-pr` | | Commit, push, and create a PR |
| `/diff` | | View uncommitted changes |
| `/review` | | Review a pull request |
| `/pr-comments` | | Get PR comments |
| `/security-review` | | Security audit of current branch |
| `/ultrareview` | | 10-20 min remote deep bug hunt |
| `/batch` | | Parallel agents across entire codebase |
| `/plan` | | Enter plan mode |
| `/rewind` | `/checkpoint` | Restore code AND conversation to any point |
| `/branch` | `/fork` | Branch the conversation |

### Configuration
| Command | Aliases | What It Does |
|---------|---------|-------------|
| `/config` | `/settings` | Open config panel |
| `/model` | | Change AI model |
| `/effort` | | Set effort level (low/medium/high/**max**) |
| `/fast` | | Toggle Penguin Mode |
| `/advisor` | | Configure a SECOND AI model alongside Claude |
| `/permissions` | `/allowed-tools` | Manage tool permission rules |
| `/sandbox` | | Toggle bash sandboxing |
| `/theme` | | Change theme |
| `/color` | | Set prompt bar color for session |
| `/vim` | | Toggle vim keybindings |
| `/voice` | | Toggle voice mode |
| `/privacy-settings` | | Privacy controls |
| `/hooks` | | View hook configurations |
| `/keybindings` | | Customize keybindings |
| `/terminal-setup` | | Set up terminal key binding |
| `/extra-usage` | | Configure extra usage when limits hit |

### Memory & Context
| Command | Aliases | What It Does |
|---------|---------|-------------|
| `/memory` | | Edit persistent memory files |
| `/files` | | List files currently in context |
| `/context` | | Visualize context as a colored grid |
| `/export` | | Export conversation to file |
| `/copy` | | Copy last response (`/copy N` for Nth) |
| `/rename` | | Rename conversation |
| `/tag` | | Toggle searchable tag on session |
| `/resume` | `/continue` | Resume a previous conversation |

### Integrations
| Command | Aliases | What It Does |
|---------|---------|-------------|
| `/mcp` | | Manage MCP servers |
| `/ide` | | Manage IDE integrations |
| `/chrome` | | Chrome automation settings |
| `/install-github-app` | | GitHub Actions setup |
| `/install-slack-app` | | Slack app install |
| `/remote-control` | `/rc` | Remote control sessions |
| `/remote-env` | | Configure remote environment |
| `/session` | `/remote` | Show remote URL + QR code |
| `/desktop` | `/app` | Continue in Desktop app |
| `/mobile` | `/ios`, `/android` | QR code for mobile app |
| `/web-setup` | | Setup Claude Code on web |
| `/add-dir` | | Add working directory |

### Hidden Gems
| Command | What It Does |
|---------|-------------|
| `/heapdump` | Dump the JS heap to ~/Desktop |
| `/passes` | Give friends a FREE week of Claude Code |
| `/stickers` | Order Claude Code stickers |
| `/think-back` | Your 2025 Claude Code Year in Review |
| `/thinkback-play` | Play the thinkback animation |
| `/btw` | Quick side question without interrupting flow |
| `/skills` | List available skills |
| `/init` | Initialize a new skill |
| `/reload-plugins` | Activate pending plugin changes |

### Agent & Tasks
| Command | Aliases | What It Does |
|---------|---------|-------------|
| `/tasks` | `/bashes` | List and manage background tasks |
| `/agents` | | Manage agent configurations |

### Built-in Skills
| Skill | What It Does |
|-------|-------------|
| `/simplify` | Review code for quality and efficiency |
| `/verify` | Verify a code change works |
| `/batch` | Parallel work orchestration |
| `/loop` | Run a command on recurring interval |
| `/schedule` | Cron-based scheduled agents |
| `/debug` | Enable debug logging |
| `/stuck` | Diagnose frozen sessions |
| `/remember` | Organize memory landscape |
| `/skillify` | Capture current process as reusable skill |
| `/claude-api` | Build apps with Claude API/SDK |
| `/claude-in-chrome` | Chrome browser automation |
| `/lorem-ipsum` | Generate placeholder text |

### Internal-Only Commands (Anthropic Employees)
| Command | What It Does |
|---------|-------------|
| `/ant-trace` | Trace internal operations |
| `/autofix-pr` | Auto-fix PR issues |
| `/backfill-sessions` | Backfill session data |
| `/break-cache` | Clear internal caches |
| `/bughunter` | Bug hunting mode |
| `/ctx-viz` | Context visualization |
| `/mock-limits` | Mock usage limits for testing |
| `/bridge-kick` | Inject bridge failure states |
| `/insights` | Analyze Claude Code session data |
| `/teleport` | Teleport to different environment |
| `/debug-tool-call` | Debug tool calls |
| `/reset-limits` | Reset rate limits |

### Feature-Gated Commands
| Command | Gate | What It Does |
|---------|------|-------------|
| `/brief` | KAIROS | Brief output mode |
| `/assistant` | KAIROS | Assistant mode |
| `/bridge` | BRIDGE_MODE | Bridge mode |
| `/voice-command` | VOICE_MODE | Voice command |
| `/force-snip` | HISTORY_SNIP | Force message snipping |
| `/workflows` | WORKFLOW_SCRIPTS | Workflow scripts |
| `/subscribe-pr` | KAIROS_GITHUB_WEBHOOKS | Subscribe to PR updates |
| `/ultraplan` | ULTRAPLAN | 30-min cloud planning |
| `/torch` | TORCH | Unknown (unreleased) |
| `/peers` | UDS_INBOX | Peer agent communication |
| `/buddy` | BUDDY | Tamagotchi companion |
| `/proactive` | PROACTIVE | Proactive suggestions |

---

## 60+ Keyboard Shortcuts

### Global
| Shortcut | Action |
|----------|--------|
| `Ctrl+C` | Interrupt (double-press to force) |
| `Ctrl+D` | Exit (double-press to force) |
| `Ctrl+L` | Redraw screen |
| `Ctrl+T` | Toggle task view |
| `Ctrl+O` | Toggle transcript mode |
| `Ctrl+R` | Search command history |
| `Ctrl+B` | Background a running task |
| `Ctrl+Shift+B` | Toggle brief mode (KAIROS) |
| `Ctrl+Shift+O` | Toggle teammate preview |
| `Ctrl+Shift+F` | Global file search (QUICK_SEARCH) |
| `Ctrl+Shift+P` | Quick open (QUICK_SEARCH) |
| `Meta+J` | Toggle terminal panel |

### Chat Input
| Shortcut | Action |
|----------|--------|
| `Escape` | Cancel input |
| `Enter` | Submit message |
| `Shift+Tab` | Cycle input modes |
| `Meta+P` | Model picker |
| `Meta+O` | Toggle fast mode (Penguin Mode) |
| `Meta+T` | Toggle thinking |
| `Ctrl+X Ctrl+K` | Kill all running agents (chord) |
| `Ctrl+G` | Open external editor |
| `Ctrl+X Ctrl+E` | Open external editor (alt chord) |
| `Ctrl+S` | Stash current input |
| `Alt+V` / `Ctrl+V` | Paste image from clipboard |
| `Up/Down` | Command history |
| `Ctrl+Shift+-` | Undo |
| `Space` (hold) | Push-to-talk voice (VOICE_MODE) |

### Scrolling
| Shortcut | Action |
|----------|--------|
| `PageUp/PageDown` | Page scroll |
| `Ctrl+Home` | Jump to top |
| `Ctrl+End` | Jump to bottom |
| `Ctrl+Shift+C` | Copy selection |

### History Search (Ctrl+R)
| Shortcut | Action |
|----------|--------|
| `Ctrl+R` | Next result |
| `Escape/Tab` | Accept and close |
| `Enter` | Execute selected |

### Settings Menu
| Shortcut | Action |
|----------|--------|
| `J` / `K` | Navigate (vim-style) |
| `Space` | Toggle setting |
| `Enter` | Save and close |
| `/` | Search settings |

All shortcuts are customizable via `~/.claude/keybindings.json`. Chord bindings are supported (e.g., `Ctrl+X Ctrl+K`).

---

## 60+ Feature Flags

These compile-time gates control what features are visible in your installation:

### Major Systems
| Flag | What It Controls |
|------|-----------------|
| `BUDDY` | Tamagotchi pet companion |
| `KAIROS` | Always-on persistent assistant |
| `KAIROS_BRIEF` | Brief output mode |
| `KAIROS_CHANNELS` | Channel notifications |
| `KAIROS_DREAM` | Dream memory consolidation |
| `KAIROS_GITHUB_WEBHOOKS` | GitHub webhook PR monitoring |
| `KAIROS_PUSH_NOTIFICATION` | Push notifications |
| `PROACTIVE` | Proactive agent mode |
| `ULTRAPLAN` | 30-min remote cloud planning |
| `COORDINATOR_MODE` | Multi-agent swarm orchestration |
| `VOICE_MODE` | Voice dictation input |
| `BRIDGE_MODE` | Remote control from claude.ai |
| `DAEMON` | Background daemon mode |
| `TRANSCRIPT_CLASSIFIER` | AFK mode / ML auto-approval |
| `WORKFLOW_SCRIPTS` | Workflow automation |

### Tools & UI
| Flag | What It Controls |
|------|-----------------|
| `WEB_BROWSER_TOOL` | Browser automation |
| `MONITOR_TOOL` | MCP server monitoring |
| `TERMINAL_PANEL` | Built-in terminal panel |
| `QUICK_SEARCH` | Cmd+Shift+F / Cmd+Shift+P |
| `MESSAGE_ACTIONS` | Message action shortcuts |
| `HISTORY_SNIP` | History snipping |
| `HISTORY_PICKER` | History selection UI |
| `MCP_SKILLS` | MCP-based skills |
| `EXPERIMENTAL_SKILL_SEARCH` | Skill discovery |
| `CHICAGO_MCP` | Computer Use |

### Infrastructure
| Flag | What It Controls |
|------|-----------------|
| `TORCH` | Unknown (unreleased) |
| `UDS_INBOX` | Agent peer messaging |
| `FORK_SUBAGENT` | Fork subagent capability |
| `LODESTONE` | Deep link support |
| `AGENT_TRIGGERS` | Scheduled agent triggers |
| `AGENT_TRIGGERS_REMOTE` | Remote agent triggers |
| `AGENT_MEMORY_SNAPSHOT` | Agent memory snapshots |
| `EXTRACT_MEMORIES` | Automatic memory extraction |
| `FILE_PERSISTENCE` | File persistence across sessions |
| `NATIVE_CLIENT_ATTESTATION` | Client authenticity verification |
| `CCR_AUTO_CONNECT` | Auto cloud container connection |
| `CCR_MIRROR` | Cloud container mirroring |

---

## Environment Variables That Matter

### Authentication & API
| Variable | What It Does |
|----------|-------------|
| `ANTHROPIC_API_KEY` | API key |
| `ANTHROPIC_BASE_URL` | Custom API endpoint |
| `ANTHROPIC_MODEL` | Override default model |
| `CLAUDE_CODE_USE_BEDROCK` | Use AWS Bedrock |
| `CLAUDE_CODE_USE_VERTEX` | Use Google Vertex AI |
| `CLAUDE_CODE_USE_FOUNDRY` | Use Anthropic Foundry |

### Power User
| Variable | What It Does |
|----------|-------------|
| `CLAUDE_CODE_EFFORT_LEVEL` | Set effort: low/medium/high/**max** (max = internal only) |
| `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY` | Parallel tool calls (default is low) |
| `CLAUDE_CODE_MAX_CONTEXT_TOKENS` | Max context window |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | Max output length |
| `CLAUDE_CODE_ALWAYS_ENABLE_EFFORT` | Effort level always active |
| `CLAUDE_CODE_EAGER_FLUSH` | Faster output streaming |

### Debug & Visibility
| Variable | What It Does |
|----------|-------------|
| `CLAUDE_CODE_DEBUG_LOG_LEVEL` | Verbosity: verbose/debug/info/warn/error |
| `CLAUDE_CODE_DEBUG_LOGS_DIR` | Custom debug log directory |
| `CLAUDE_CODE_PERFETTO_TRACE` | Perfetto performance trace |

### Disable Features
| Variable | What It Does |
|----------|-------------|
| `CLAUDE_CODE_DISABLE_THINKING` | Disable extended thinking |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY` | Disable dream/memory consolidation |
| `CLAUDE_CODE_DISABLE_FAST_MODE` | Disable Penguin Mode |
| `CLAUDE_CODE_DISABLE_MOUSE` | Disable mouse support |
| `CLAUDE_CODE_DISABLE_PROMPT_CACHING` | Disable prompt cache |
| `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` | Disable background tasks |

### Internal / Secret
| Variable | What It Does |
|----------|-------------|
| `USER_TYPE=ant` | Unlocks ALL internal Anthropic features |
| `CLAUDE_CODE_UNDERCOVER` | Force undercover mode ON |
| `CLAUDE_INTERNAL_FC_OVERRIDES` | Override feature flag checks |
| `IS_DEMO` | Demo mode |

---

## 54+ Internal Tools

Beyond the visible tools (Read, Write, Edit, Bash, Grep, Glob), Claude Code has dozens more:

### Always Available
`FileReadTool` · `FileEditTool` · `FileWriteTool` · `GlobTool` · `GrepTool` · `BashTool` · `AgentTool` · `SendMessageTool` · `WebFetchTool` · `WebSearchTool` · `NotebookEditTool` · `AskUserQuestionTool` · `SkillTool` · `ToolSearchTool`

### Task Management
`TaskCreateTool` · `TaskGetTool` · `TaskListTool` · `TaskUpdateTool` · `TaskOutputTool` · `TaskStopTool`

### Planning
`EnterPlanModeTool` · `ExitPlanModeV2Tool` · `BriefTool`

### Multi-Agent
`TeamCreateTool` · `TeamDeleteTool`

### MCP
`ListMcpResourcesTool` · `ReadMcpResourceTool` · `MCPTool` · `McpAuthTool`

### Scheduling
`CronCreateTool` · `CronDeleteTool` · `CronListTool` · `RemoteTriggerTool`

### Worktree
`EnterWorktreeTool` · `ExitWorktreeTool`

### Feature-Gated
`WorkflowTool` · `MonitorTool` · `SnipTool` · `ListPeersTool` · `CtxInspectTool` · `TerminalCaptureTool` · `SleepTool` · `WebBrowserTool` · `LSPTool` · `PowerShellTool` · `REPLTool`

### Internal Only (Anthropic Employees)
`ConfigTool` · `TungstenTool` · `SuggestBackgroundPRTool`

### KAIROS-Exclusive
`SendUserFileTool` · `PushNotificationTool` · `SubscribePRTool`

---

## Built-in Agent Types

| Agent | What It Does |
|-------|-------------|
| `general-purpose` | Multi-step research and code execution |
| `Explore` | Fast file search specialist (read-only) |
| `Plan` | Software architect for planning (read-only) |
| `verification` | Adversarial testing specialist |
| `claude-code-guide` | Documentation and API help |

Custom agents can be loaded from `~/.claude/agents/`.

---

## Permission Modes

| Mode | What It Does |
|------|-------------|
| `default` | Asks permission for everything |
| `plan` | Write plan first, execute on approval |
| `acceptEdits` | Auto-approve file edits, ask for shell |
| `dontAsk` | Only ask for destructive operations |
| `bypassPermissions` | Full autonomy, no prompts |
| `auto` | ML-based auto-approval (experimental) |

---

## Unreleased Beta API Headers

Found in the constants:

| Beta Header | Feature |
|-------------|---------|
| `interleaved-thinking-2025-05-14` | Extended thinking |
| `context-1m-2025-08-07` | 1M token context window |
| `structured-outputs-2025-12-15` | Structured output format |
| `redact-thinking-2026-02-12` | Redacted/hidden thinking |
| `token-efficient-tools-2026-03-28` | Token-efficient tool schemas |
| `afk-mode-2026-01-31` | AFK unattended mode |
| `advisor-tool-2026-03-01` | Advisor dual-model tool |
| `fast-mode-2026-02-01` | Penguin Mode |

---

## How This Was Found

The Claude Code source code ships with the npm package. Running `npm install @anthropic-ai/claude-code` (or just installing Claude Code) gives you the full source — compiled JavaScript with all feature flags, internal tools, telemetry events, system prompts, and configuration schemas intact.

This repository documents what's in there. All findings are from the publicly available package.

---

## Disclaimer

This is for **educational and research purposes**. All information was obtained from publicly available source code distributed via npm. No systems were accessed without authorization. This documents what Anthropic ships to every Claude Code user.

---

*If you found this useful, star the repo and share it.*

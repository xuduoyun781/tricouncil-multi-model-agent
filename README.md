# TriCouncil Multi-Model Agent

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

An open-source, serverless skill/plugin that lets Codex and WorkBuddy coordinate multiple AI models through staged execution, independent review, bug fixing, and final delivery.

## Why TriCouncil?

- Use 2, 3, or more model APIs in one workflow.
- Give every model its own provider, endpoint, model name, role, and system prompt.
- Assign models as workers or reviewers for each stage.
- Enable, disable, add, edit, or remove models at any time.
- Keep API keys outside Git, prompts, and task logs.
- Run without a web interface or persistent backend.
- Install the same self-contained skill in Codex and WorkBuddy.

## Install after cloning

```bash
git clone git@github.com:xuduoyun781/tricouncil-multi-model-agent.git
cd tricouncil-multi-model-agent

# Recommended: install and immediately open the secure setup wizard
./install.sh codex --setup
./install.sh workbuddy --setup

# Install both hosts and configure once
./install.sh all --setup
```

Windows PowerShell:

```powershell
.\install.ps1 codex -Setup
.\install.ps1 workbuddy -Setup
.\install.ps1 all -Setup
```

For an update, add `--force` (`-Force` in PowerShell). The installer backs up the existing skill before replacing it.

## Configure models and prompts

The setup wizard asks, for each model:

1. Whether it is enabled.
2. Provider type: OpenAI-compatible, Anthropic, or Gemini.
3. Model name and API endpoint.
4. API key through hidden terminal input.
5. Role and dedicated system prompt.
6. Which stages it executes or reviews.
7. Which enabled model coordinates stage results.

Press Enter to keep a recommended default. Reopen configuration at any time:

```bash
# Codex
python3 ~/.codex/skills/tricouncil/scripts/tricouncil.py manage

# WorkBuddy / CodeBuddy
python3 ~/.codebuddy/skills/tricouncil/scripts/tricouncil.py manage
```

You can also ask the host agent naturally:

> Add a DeepSeek model as a code reviewer in TriCouncil.

> Disable Gemini and replace the primary model prompt.

> Configure the TriCouncil APIs and stage roles.

API keys should never be pasted into chat. The skill routes key entry to a hidden terminal prompt.

## How it works

```text
Task
  ↓
Planning: workers run in parallel → independent reviewers → coordinator synthesis
  ↓
Execution: workers run in parallel → independent reviewers → coordinator synthesis
  ↓
Verification: validators inspect results → other models review the validation
  ↓
Repair & delivery: fixes, tests, packaging plan → final cross-review
```

If a configured stage worker is disabled, TriCouncil selects an enabled fallback. At least two models must remain enabled so that independent review is still possible.

## Supported APIs

- OpenAI and OpenAI-compatible Chat Completions endpoints
- Anthropic Messages API
- Google Gemini `generateContent`
- Local demo provider for tests without paid API calls

## Security

- Secrets are stored in `~/.config/tricouncil/secrets.json` with user-only permissions.
- Model settings and prompts are stored in `~/.config/tricouncil/config.json`.
- Secrets are never written to this repository, task prompts, or run logs.
- Disabled models are not called and incur no API cost.
- `self-test` uses local demo agents and never calls a paid API.

## Repository layout

```text
plugins/tricouncil-agent/
├── plugin.json
├── .codex-plugin/plugin.json
└── skills/tricouncil/
    ├── SKILL.md
    ├── agents/openai.yaml
    ├── scripts/tricouncil.py
    └── assets/

.agents/plugins/marketplace.json
install.py
install.sh
install.ps1
```

## Validate locally

```bash
python3 plugins/tricouncil-agent/skills/tricouncil/scripts/tricouncil.py self-test
```

## License

MIT

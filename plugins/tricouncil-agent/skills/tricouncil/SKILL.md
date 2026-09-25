---
name: tricouncil
description: Run tasks through 2–3 independently prompted AI models with staged execution, cross-review, repair, and delivery. Use for multi-model collaboration, model verification, staged AI work, or a main model plus reviewer/fixer models. Do not use for simple questions that do not justify multiple paid calls.
---

# TriCouncil

Use the bundled local runner. It needs no website or persistent server.

Resolve the directory containing this `SKILL.md` as `<skill-root>`, then run commands with:

```bash
python3 <skill-root>/scripts/tricouncil.py <command>
```

Never ask the user to paste API keys into chat or task text.

## Configure

- Easiest option: run `manage` for an interactive menu covering models, prompts, keys, and on/off switches.
- First use: run `setup` in an interactive terminal. It uses hidden input for keys.
- Inspect configuration: run `status` or `doctor`.
- Change one key: run `configure-key NAME`.
- Delete one stored key: run `remove-key NAME`.
- Toggle a model: run `enable AGENT_ID` or `disable AGENT_ID`.
- Add, edit, or delete model slots with `add-model`, `edit-model AGENT_ID`, and `remove-model AGENT_ID`.
- Replace a role prompt with `set-prompt AGENT_ID`; finish multiline input with a line containing only `.`.
- Change an API/model non-interactively with `set-model AGENT_ID --model MODEL` and optional provider, URL, or key-name flags.
- Advanced users may directly edit `~/.config/tricouncil/config.json`.

Do not invoke paid APIs merely to test installation. Run `self-test`, which uses local demo models.

## Execute

For a multi-model task, write the complete goal, inputs, constraints, deliverables, and acceptance criteria to a UTF-8 workspace file. Then run:

```bash
python3 <skill-root>/scripts/tricouncil.py run --task-file <absolute-task-file>
```

Use `--output <absolute-directory>` when the user chose a destination. Otherwise results go to `.tricouncil-runs/<timestamp>/` in the current directory.

Read `final.md` and `run.json` after completion. Report the final result, completed agents and stages, failures or unresolved findings, and output directory.

Do not claim that an external model edited workspace files merely because it proposed edits. Apply changes only when the user's request authorizes Codex to edit them, then verify normally.

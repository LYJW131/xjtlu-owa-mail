# AGENTS.md

This repository is a single [Agent Skill](https://agentskills.io/specification). The skill contract lives in [SKILL.md](SKILL.md); read it before doing anything with the mailbox. Codex, Cursor, OpenCode and other agents that pick up `AGENTS.md` should treat `SKILL.md` as the instructions and `scripts/owa` as the only entry point.

## Layout

| Path | Purpose |
| --- | --- |
| `SKILL.md` | Frontmatter (`name`, `description`, `license`, `compatibility`, `metadata`) + agent instructions |
| `scripts/owa` | Bash launcher: bootstraps `.venv`, then runs `scripts/owa_cli.py` |
| `scripts/owa_cli.py` | Subcommands; JSON on stdout, logs on stderr |
| `references/api.md` | Python library API, EWS JSON dialect, login chain |
| `xjtlu_owa_mail/` | Python package (auth cache, Microsoft SSO, OWA client, thin UIM wrapper) |
| `.claude-plugin/` | Plugin + marketplace manifests for `/plugin marketplace add` |
| `.env` | Local credentials, never committed (see `.env.example`) |

UIM login itself is maintained separately in [xjtlu-uim-login](https://github.com/LYJW131/xjtlu-uim-login) and pulled in as a dependency.

## Rules for changing this repo

- Keep the version identical in `SKILL.md` (`metadata.version`), `pyproject.toml` and `.claude-plugin/plugin.json`.
- `scripts/owa_cli.py` must keep stdout JSON-only. New progress output goes through `xjtlu_owa_mail.log.log()` (stderr).
- Anything that sends mail (`send`, `reply`, `forward`) defaults to `body_type="auto"`: plain text stays plain text so line breaks survive. Do not change the default back to HTML.
- Test against a real mailbox by sending to yourself, then move the test messages to Deleted Items; never hard-delete other mail.
- Before publishing, run:

```bash
skills-ref validate "$(pwd)"     # pip install "skills-ref @ git+https://github.com/agentskills/agentskills.git#subdirectory=skills-ref"
claude plugin validate . --strict
```

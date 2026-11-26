# Claude Code Configuration

This file configures Claude Code's behavior in this repository.

## Loaded Skills

Custom skills are in `./skills/`. They are loaded automatically:
- `caveman-lite`: Token-efficient communication
- `lm-ready-template`: Documentation for replicating this setup

## Rules Override

This `.claude/CLAUDE.md` applies ONLY within Claude Code sessions on this repo. It inherits from the root `CLAUDE.md` and adds Claude-Code-specific rules.

### Session-Specific

- Do not add new files outside of features listed in CLAUDE.md
- Prefer git branches for feature work
- Always commit before pushing

## MCP Servers

- **metasploit-mcp**: Configured for Kelly (Kali VM). In cloud sessions, it displays a setup message. See `kelly/metasploit-mcp-setup.md` for full installation.

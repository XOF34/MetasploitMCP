# Claude-Codex-Handoff: LLM-Ready Repository

## Environment Detection

This repository works in three contexts. Claude Code automatically detects which one based on the hostname and environment.

### Cloud Sessions
- Hostname: contains "claude" or is unknown
- Bash tool: unrestricted
- Network: proxy to allowed hosts
- **Rules:** Keep work local unless explicitly confirmed

### Kali VM "Karla"
- Hostname: "karla" or contains "kali"
- Bash tool: full access, outbound network works
- **Rules:** `apt` available, Metasploit native package, no GPU

### macOS "H34"
- Hostname: "h34" or contains "mac"
- Bash tool: sandboxed (no outbound, no sudo, no GPU)
- **Rules:** Hand user Terminal commands, MLX/PyTorch needs Terminal

## Global Rules

- Address user as **sir**
- Keep work local (no GitHub/Slack posts without explicit confirmation)
- Prefer editing existing files over creating new ones
- No comments unless "why" is non-obvious
- Setup guides: dense, opinionated, copy-paste-ready, assume expertise

## This Session's Custom Skills

Custom skills live in `.claude/skills/`. They load automatically on session start. See `docs/superpowers/IMPLEMENTATION-GUIDE.md` for the structure.

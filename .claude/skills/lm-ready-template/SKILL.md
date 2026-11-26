---
name: lm-ready-template
description: Guide to replicating this LLM-ready repository structure in your other repos. Use when setting up new repos or documenting the pattern.
---

# LLM-Ready Repository Template

This skill documents how to replicate the claude-codex-handoff setup.

## Three Layers

**Layer 1: Root CLAUDE.md**
- Machine detection (cloud, Kali, macOS)
- Global rules

**Layer 2: .claude/ folder**
- CLAUDE.md (Claude Code specific)
- settings.json (permissions, skill paths)

**Layer 3: .claude/skills/**
- Each skill is a folder with SKILL.md
- Loaded automatically

## Replication Steps

1. Copy root CLAUDE.md pattern
2. Create .claude/CLAUDE.md and settings.json
3. Add skills to .claude/skills/
4. Commit and register repo
5. Verify in Claude Code session (system-reminder shows CLAUDE.md loaded)

See `docs/superpowers/IMPLEMENTATION-GUIDE.md` for exact copy-paste examples.

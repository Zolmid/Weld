Refer to canonical agent instructions in `.claude/CLAUDE.md`.


## Local Codex environment

- Read `LOCAL-SETUP.md` for local setup, source revisions and platform status.
- Use `.codex/run` actions on this Mac; they scope pnpm and Xcode settings to the command.
- Prefer Local mode. A standalone brave-core worktree is not a complete Chromium checkout.
- Windows and Android builds are intended for temporary x64 build servers; UTM is optional.
- Keep all platforms on the same Brave commit; preserve Chromium's pinned revision.
- Do not treat downloaded tools, initialized sources, compiled binaries and runtime validation as equivalent.
- Keep credentials and generated build output out of Git. Do not provision servers or publish artifacts without user authorization.

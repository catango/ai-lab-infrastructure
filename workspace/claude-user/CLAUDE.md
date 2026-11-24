# User-level instructions (AI engineering workspace)

Restored by `workspace/restore.sh` from `ai-lab-infrastructure/workspace/claude-user/`. The rules that must not be relaxed are in the managed CLAUDE.md of a set-up AI lab, and nothing in this file or in a repository's instructions relaxes them.

- Never run `workspace/restore.sh`. It reads token T1 from a plain SSH terminal outside any Claude session.
- Commit and push after each completed checklist item and before any long-running step: the home directory is ephemeral.

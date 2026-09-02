# GSD workflow overlay

Shared and unit-specific repository instructions live in root and nested `CLAUDE.md`
files. This overlay owns GSD workflow only.

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

GSD routing is enforced by the `gsd-workflow-guard` PreToolUse hook; do not duplicate it here. `/gsd-debug` for investigation, `/gsd-execute-phase` for planned phase work. Root `CLAUDE.md` is the agent source of truth; this file is the GSD overlay (`claude_md_path`).
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

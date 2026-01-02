# Development Guidelines

## Source of truth for Mainsail coding rules

The Mainsail upstream project maintains AI/developer guidelines here:

- https://github.com/mainsail-crew/mainsail/blob/develop/AGENTS.md

In short: Vue 2 class components, strict TypeScript, Vuetify 2 patterns, `@/` imports, i18n for all strings.

## StitchLAB-specific guidelines

- Prefer adding StitchLAB “glue” docs and runbooks in `docs/` (this folder).
- Avoid mixing StitchLAB docs into upstream project docs unless strictly necessary.
- Keep any “expected-but-not-implemented” UX explicit (example: live control WebSocket `:7150`).

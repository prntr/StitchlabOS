# Development Guidelines

## Source of truth for Mainsail coding rules

The Mainsail upstream project maintains AI/developer guidelines here:

- https://github.com/mainsail-crew/mainsail/blob/develop/AGENTS.md

In short: Vue 2 class components, strict TypeScript, Vuetify 2 patterns, `@/` imports, i18n for all strings.

## StitchLAB-specific guidelines

- Prefer adding StitchLAB “glue” docs and runbooks in `docs/` (this folder).
- Avoid mixing StitchLAB docs into upstream project docs unless strictly necessary.
- Keep any “expected-but-not-implemented” UX explicit (example: live control WebSocket `:7150`).

## TurtleStitch development

- If the change is about TurtleStitch itself (blocks, language features, export),
  use upstream docs in `turtlestitch/docs/` and keep local docs minimal.
- Default order for development guidance:
  - `turtlestitch/docs/README.md`
  - `turtlestitch/docs/Extensions.md`
  - `turtlestitch/docs/API.md`
  - `turtlestitch/docs/CONTRIBUTING.md`

## Documenting new components

- Add a focused component page under `docs/components/` with: status, runtime location, entry points, config, and verification steps.
- Keep the doc scoped to the component; only mention integrations that directly affect it.
- Update the index page: `docs/README.md`.

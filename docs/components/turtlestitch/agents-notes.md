# TurtleStitch Agent Notes

## Scope

- This workspace hosts TurtleStitch as an offline app on the Pi.
- Any changes to Snap!/TurtleStitch behavior belong to upstream docs in `turtlestitch/docs/`.

## Where to start (upstream)

- `turtlestitch/docs/README.md` for the extension-first approach.
- `turtlestitch/docs/Extensions.md` for new blocks/menus/buttons.
- `turtlestitch/docs/API.md` for embedding and external control.
- `turtlestitch/docs/CONTRIBUTING.md` for style rules and JSLint settings.

## Integration boundaries (local)

- Hosting: nginx serves `/home/pi/turtlestitch` on port `3000`.
- Mainsail only links to TurtleStitch; it does not embed or modify it.

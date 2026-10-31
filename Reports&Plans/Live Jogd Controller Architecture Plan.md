# Plan - Live Jogd Controller Architecture

## Context

The Cross-Platform Mainsail Connection Stability plan intentionally keeps the `live_jogd` work narrow: no automatic boot start, no frontend auto-connect to `:7150`, explicit user-triggered service start/stop, and reduced Moonraker load while active.

This document tracks the larger controller architecture work that is **not required** to declare the stability batch complete. It is a product and firmware architecture plan.

## Implementation Decision (2026-05-10)

The first implementation slice is intentionally conservative:

- Live Control state lives in `live_jogd` memory only and defaults to off after service start, service restart, a fresh browser/client session, meaningful controller selection/type changes, and sustained controller-link timeout. Idempotent selection/type updates do not reset the gate.
- Controller type detection uses a staged source-of-truth model:
  - firmware-provided `controller_type` / `peer_type` when present,
  - optional `CONTROLLER_TYPE_BY_MAC` / `CONTROLLER_TYPE_BY_OUI` config maps for old firmware,
  - manual runtime labels from the Controller menu.
- Manual labels are not persisted yet. This preserves the safest restart behavior while allowing old gamepad prototypes to be enabled for testing.
- Unknown controllers remain status/pairing only and cannot move axes or run motion macros.
- Emergency stop remains available regardless of Live Control.
- Homing, XY jog, Z jog, `STITCH`, and `NEEDLE_TOGGLE` are gated by Live Control plus per-type policy.
- Initial per-type policy:
  - `gamepad`: XY, Z, homing, stitch, and needle toggle.
  - `foot_pedal`: stitch and needle toggle only; no XY movement in this slice.
  - `unknown`: no motion or motion macros.

Implemented files:

- `stitchlabos/image/src/modules/live-jogd/filesystem/home/pi/live_jogd/config.py`
- `stitchlabos/image/src/modules/live-jogd/filesystem/home/pi/live_jogd/dongle_api.py`
- `stitchlabos/image/src/modules/live-jogd/filesystem/home/pi/live_jogd/live_jogd.py`
- `mainsail/src/components/TheControllerMenu.vue`
- `mainsail/src/plugins/controllerWebSocket.ts`
- `mainsail/src/store/server/controller/`
- `mainsail/src/locales/en.json`

## Goals

- Define a clear controller lifecycle with separate states for service availability, pairing/status, and motion-enabled control.
- Add an explicit Live Control gate so no controller can move the machine merely because `live_jogd` is running.
- Identify controller types reliably enough for safe per-type behavior.
- Keep old firmware, dongle-less systems, and unknown controllers safe by default.
- Preserve normal Mainsail behavior when the controller system is stopped or unavailable.

## Lifecycle Model

The target model has three states:

1. **Stopped**
   - `live_jogd` is not running.
   - Mainsail does not open `:7150`.
   - Controller menu offers an initialization action.
   - No controller traffic or Moonraker polling comes from `live_jogd`.

2. **Status-only**
   - User has started `live_jogd`.
   - Mainsail connects to the controller WebSocket after service/WS readiness.
   - Dongle status, peer list, pairing, WiFi, and diagnostic controls are available.
   - Motion commands are rejected in the backend unless Live Control is explicitly enabled.

3. **Motion-enabled**
   - User explicitly enables Live Control.
   - Backend enforces Live Control plus the existing deadman, homed, idle, and link-health checks.
   - Per-type behavior controls which axes/actions are accepted.
   - Disabling Live Control immediately zeroes velocity state and rejects further motion.

## Live Control Gate

Resolved for the first implementation slice:

- Live Control state lives in `live_jogd` memory only for safest default-off restart behavior.
- Moonraker DB is not used for Live Control persistence in this slice.
- Backend memory remains the enforcement source if a future UI preference is added.
- Define frontend controls:
  - Show Live Control only after service and dongle are connected.
  - Default off after service start, a fresh browser/client session, service restart, dongle reconnect, or sustained link timeout.
  - Show status/pairing independently from motion enablement.
Backend enforcement:

- `_can_jog()` checks Live Control, active controller type, active-link health, idle state, deadman, and homed axes before accepting XY jog.
- Z jog, homing, `STITCH`, and `NEEDLE_TOGGLE` check Live Control and per-type policy before emitting G-code.
- Emergency stop remains available regardless of Live Control state.

## Controller Type Detection

The implementation uses a staged combination:

1. **Firmware `peer_type` extension**
   - Dongle/controller firmware adds a `peer_type` byte to pairing and peer-list data.
   - Best long-term source of truth.
   - Requires firmware updates and compatibility handling for old peers.

2. **Server-side MAC/type mapping**
   - `live_jogd` maps full MACs or OUIs to controller types from config.
   - Fastest path without firmware changes.
   - Requires maintenance as hardware variants ship.

3. **Manual user labeling**
   - UI asks the user to label newly paired controllers.
   - Store labels in Moonraker DB or a `live_jogd` config file.
   - Works with old firmware but depends on user correctness.

Default safety rule: unknown type means status/pairing only, no motion.

## Per-Type Behavior

Initial behavior targets:

- **Gamepad**
  - Full guarded XYZ jog.
  - XY requires deadman, homed axes, idle printer state, Live Control enabled, and healthy link.
  - Z/button actions must use the same Live Control policy chosen above.

- **Foot pedal**
  - Sewing/stitch/Z behavior only.
  - No XY movement.
  - Pedal release or link loss must stop motion promptly.
  - Final behavior depends on the sewing-mode and encoder plans.

- **Unknown controller**
  - May appear in peer list and pairing/status UI.
  - Cannot move axes or run motion macros.
  - UI should make the unknown/safe-disabled state clear.

## Compatibility And Persistence

- Old firmware without a type field must still pair and report status.
- Dongle-less Pis must have no service restart loop and no controller WebSocket traffic.
- Service restart must reset Live Control to off unless a later safety review explicitly approves persistence.
- Controller type should survive service restart when the chosen detection method supports it.
- Multiple paired peers need a clear active-peer selection model; inactive peers must not generate motion.

## Verification

Bench verification on `stitchlab` (`192.168.0.129`, 2026-05-11):

- Hot-deployed the current Mainsail build and `live_jogd` backend slice to the test machine.
- Fixed two image/deploy blockers found during the bench run:
  - `websockets` was missing from `live_jogd/requirements.txt`; the daemon could not import `websockets`.
  - Current Moonraker reads `moonraker.asvc`, but still rejects inactive `static` units that are not in `available_services`. Added a boot-time `stitchlab-moonraker-service-control-patch` so explicitly allowed services such as `live_jogd` can be started/stopped via `machine.services.*`.
- Verified `machine.services.start { service: "live_jogd" }` starts the service after the patch.
- Verified `live_jogd` opens `0.0.0.0:7150`, reports dongle status, and exposes Live Control fields over WebSocket.
- Verified Mainsail Controller menu start/connect flow:
  - UI enters connected/status mode.
  - Dongle firmware/status is shown.
  - Active controller is listed as `gamepad`.
  - Live Control defaults to `Off`.
- Verified Live Control policy over WebSocket:
  - Setting active controller to `unknown` rejects Live Control with `unknown_controller`.
  - Setting active controller to `gamepad` allows Live Control to switch on.
  - With no healthy active link, motion remains disabled with `motion_block_reason: "link_inactive"`.
  - Switching Live Control off returns `live_control_enabled: false` and `motion_block_reason: "live_control_off"`.
- Follow-up bench fix after gamepad testing:
  - Short normal controller-frame gaps were tripping the 200 ms link watchdog and turning Live Control off immediately after actions.
  - `LINK_TIMEOUT_S` now still zeroes motion and blocks movement promptly, but Live Control only latches off after `LIVE_CONTROL_LINK_TIMEOUT_S` of sustained link loss.
  - Re-sending the same controller type (`gamepad` -> `gamepad`) and connecting a second WebSocket client no longer disable Live Control.
- Verified UI stop flow:
  - `machine.services.stop { service: "live_jogd" }` stops the service.
  - Port `7150` closes.
  - Mainsail remains connected to Moonraker.
  - Controller menu returns to `Service Offline` and no further reconnect errors appeared after stop.

Observed but not resolved in this bench run:

- Dongle/controller link remained inactive during the test (`link_active: false`), so guarded real XY/Z motion was not exercised.
- Journal showed intermittent serial read errors and one CRC mismatch while the service was running. This may be hardware/link noise or another process touching the serial port; it needs a focused dongle/controller link test.

Future acceptance tests for this architecture plan:

1. Service start enters status-only mode; no motion is accepted until Live Control is enabled.
2. Service restart resets Live Control to off.
3. Unknown controller can pair and show status but cannot move XY/Z.
4. Gamepad permits guarded XYZ jog only when Live Control, deadman, homed axes, idle state, and healthy link all pass.
5. Foot pedal cannot trigger XY motion.
6. Short link loss zeros motion state and rejects further motion without flipping Live Control off; sustained link loss disables Live Control and requires the user to re-enable it.
7. Controller type survives restart when using firmware type or stored manual labeling.
8. Old firmware without controller type remains safe and usable for status/pairing.
9. Stopping the service closes the WebSocket, clears frontend reconnect timers, releases `/dev/stitchlab-dongle`, and leaves Mainsail connected to Moonraker.

## Remaining Decisions

- Decide whether manual controller labels should persist in a `live_jogd` config file or Moonraker DB after bench testing.
- Decide whether the firmware `peer_type` extension should become mandatory for production hardware.
- Align foot-pedal behavior with the Hybrid/Sewing mode plans before implementation.
- Decide whether foot pedal should gain guarded Z movement or remain stitch/needle-only.

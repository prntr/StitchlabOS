# Plan — Cross-Platform Mainsail Connection Stability

## Implementation Status (2026-05-11)

All P0 items implemented on branch `feat/cross-platform-stability` (parent repo) and `stitchlabos/v2.17.0` (mainsail submodule). **Partially bench-verified on LAN, 2026-05-11** — hot-deployed to live test machine `stitchlab.local` (see "Deploy state" below). Tests 1, 2, 4, 5, 6, 7 green on Mac + Linux × Firefox + Chromium in LAN. Test 3 (Chromium 30-min background-soak with Memory Saver) **passed in LAN with no reconnect** — encouraging sign that P1-1 (Web Worker) may not be required for LAN deployments, but **not yet retested under AP-mode jitter where the throttling problem originally surfaced**. AP-mode verification still outstanding (see "Open verification" below).

| Item | Status | Parent commit | Submodule commit | Notes |
|------|--------|---------------|------------------|-------|
| P0-1 same-origin routing | done | `c9312db` | `903fb705` | Boot-time migration script for upgrades: `/usr/local/bin/stitchlab-mainsail-config-migrate` (idempotent, no-op on customised configs) |
| P0-2 live_jogd user-gated lifecycle | done | `2e4001e` | `b58ca9d2` | Service installed but not enabled; `live_jogd` appended to `moonraker.asvc`; Controller-menu start/stop exercised on bench; inactive-static Moonraker service-control patch added |
| P0-3 live_jogd Moonraker load | done | `56f2b61` | — | Combined `/printer/objects/query?toolhead&print_stats` + adaptive cadence (10 Hz active / 1 Hz idle, gated on `last_frame_time` + `current_deadman`). Did **not** migrate to Moonraker WebSocket subscribe — that's the "preferred" path if more headroom is needed |
| P0-4 dashboard preview | done | `10161eb` | `27af1a8d` | `EmbroideryPreview.vue` fully rewritten: hoop outline + `current_file.thumbnails` only, no gcode fetch, no parser. `PrintstatusEmbroidery.vue` reads stitch/jump/dim from `current_file` (with optional `stitchlab_intake.*` sidecar fields once the Intake service ships). `parseEmbroideryGcode.ts` retained — still used by `GCodeStudio2D.vue` |
| P0-5..P0-9 WebSocket client | done | — | `f8488bfd` | Single rewrite of `webSocketClient.ts`. Visibility/online/offline/pageshow listeners attached in constructor; `lastReceivedAt`/`lastSentAt`/`lastOpenedAt` separated; `explicitClose` flag forces reconnect after heartbeat watchdog despite `wasClean=true`; reconnects reset after 60 s healthy traffic; `[WebSocket]` `log()` helper; 30 s timeout on init-component waits via `armInitTimeout` (mirrors error-path → `addFailedInitComponent` + `removeInitComponent`) |
| P0-10 nginx + sysctl | done | `9741241` | — | Added `proxy_send_timeout 86400`, `proxy_buffering off`, `tcp_nodelay on`, `proxy_socket_keepalive on` to `/websocket`. New `/etc/sysctl.d/60-stitchlab-tcp-keepalive.conf`: 120s/15s/4 |
| P0-11 Moonraker ping override | done | `b452dc4` | — | Inline sed in `start_chroot_script` replaced with `/usr/local/bin/stitchlab-moonraker-ws-ping-patch` + boot-time `stitchlab-moonraker-ws-ping-patch.service` (`Before=moonraker.service`). Helper bails cleanly if upstream code shape changes — when Moonraker exposes the values as native config keys, helper becomes a no-op and can be replaced by `moonraker.conf` entries |

**Deploy state on `stitchlab.local` (2026-05-11):**

Hot-deployed (rsync/scp, no image rebuild) from local working tree:
- Mainsail dist (`mainsail/dist/`, built 2026-05-10 17:09 against commit `f8488bfd`) → `/home/pi/mainsail/`
- `live_jogd.service` (new `Restart=on-failure`, not `WantedBy=multi-user.target`) → `systemctl stop && disable` executed; unit is now `static` + `inactive`
- `live_jogd` backend files hot-deployed, including `websockets>=12.0` in `requirements.txt`
- nginx `/websocket` hardening + `/etc/sysctl.d/60-stitchlab-tcp-keepalive.conf` (120/15/4) applied
- `live_jogd` appended to `/home/pi/printer_data/moonraker.asvc`
- `/usr/local/bin/stitchlab-moonraker-service-control-patch` + boot-time service deployed and run once — lets Moonraker start/stop allowed inactive `static` units such as `live_jogd.service`
- `/usr/local/bin/stitchlab-mainsail-config-migrate` + boot-time service deployed and run once — migrated `config.json` to `port: null`
- `/usr/local/bin/stitchlab-moonraker-ws-ping-patch` + boot-time service deployed. **Helper currently a no-op on this Moonraker version** — it targets `moonraker/app.py`, but the running version has the file as `moonraker/components/application.py` and ships `websocket_ping_interval=30, websocket_ping_timeout=25` natively. Helper needs to be updated to handle the new path before this is reliable against future Moonraker upstream regressions, OR replaced by native `moonraker.conf` entries.
- Backup of replaced files at `/home/pi/backup-prestability-2026-05-10/` on the Pi.

**Open verification:**
- **AP-mode tests** — all LAN-green tests need to be repeated under AP-mode (Stitchlab SSID) to confirm the original cross-platform symptoms (which appeared most strongly on AP) are resolved. Especially Test 3 (Chromium background soak), which is the test P1-1 was scoped to address — if it stays green on AP too, P1-1 may be unnecessary.
- **Test 8** (Moonraker update resilience) — not run; needs an actual update cycle. Note above re: `stitchlab-moonraker-ws-ping-patch` makes this currently *fragile*: if Moonraker upstream changes the ping defaults, the helper will not catch it.
- **Test 10, 11** (controller user flow, return-to-normal) — bench-exercised on `stitchlab` / `192.168.0.129` on 2026-05-11 after hot-deploying the Live Control slice. Start/connect/status and stop/return-to-normal are green. The Live Control flapping found during gamepad testing was fixed by splitting short link gaps (`LINK_TIMEOUT_S`, zero/block motion) from sustained link loss (`LIVE_CONTROL_LINK_TIMEOUT_S`, disable gate). Real controller motion still needs a focused link/motion test.
- **Test 13** (large embroidery preview) — deferred until the new stable job-preview implementation is in place. `EmbroideryPreview.vue` is already rewritten to consume thumbnails-only (P0-4), but end-to-end test waits for the Intake-side counterpart.
- **Test 14** (G-Code Intake guardrail) — Producer side (Moonraker `stitchlab_intake` component, Phases 1–3) is shipped; Mainsail consumer (Phase 4 Files-UI + Start-Flow) is still pending. Guardrail-Tests gegen die Producer-API können bereits laufen, End-to-End-Verifikation gegen die UI hängt an Phase 4.

**Open code follow-ups:**
- **Init re-dispatch on reconnect (A5/P0-9).** Plan called for re-dispatching outstanding init modules when reconnect fires mid-init. Currently: the existing `socket/onOpen` already calls `server/init` on every reconnect, so init *does* reissue, but pre-existing waits in `this.waits[]` from before the disconnect are not explicitly purged. The 30 s init timeout will surface them as failed components — acceptable for P0, but a cleaner solution is to drop `this.waits[]` on `onclose` and let `onOpen → server/init` rebuild fresh.
- **`stitchlab-moonraker-ws-ping-patch` path drift.** Update helper for `components/application.py`, or remove it in favor of `moonraker.conf` entries if the deployed Moonraker version exposes the keys as native config.
- **Mainsail submodule push.** Submodule commits are local; push to `fork/stitchlabos/v2.17.0` separately when ready.
- **Stitchlabos-config / image-build rebake.** Hot-deploy is iteration; the underlying image module sources contain the changes but a fresh image flash is needed to verify the install path + Test 7 PWA-cached state once.
- **Moonraker service-control for inactive static units.** Bench testing found that current Moonraker reads `moonraker.asvc` but still rejects inactive `static` units not present in `available_services` with `Service 'live_jogd' not installed`. Added `stitchlab-moonraker-service-control-patch` to let explicitly allowed services start/stop via `machine.services.*`; verify this survives Moonraker updates during Test 8.
- **Pre-existing uncommitted work** (`Reports&Plans/`, `docs/hybrid/`, `.gitignore`, `stitchlabos-config`) was deliberately left out of stability commits.

P1 items are **not** done — see priority section below.

---

## Context

The Beta2 three-layer fix (kernel power-save off, Moonraker `websocket_ping_interval=30/timeout=25`, frontend keepalive + exp backoff) stabilized the Mac/Safari/Firefox path. On other clients — Windows laptops, Linux desktops, Chromium-family browsers, mobile — symptoms remain:

- "Initializing…" overlay lingers many seconds on first load.
- The UI reconnects intermittently, especially after the tab is backgrounded, the laptop sleeps, or the network blips.
- No errors visible to the user; just a flicker of "Connecting…".

This plan enumerates **every plausible cause** and prioritises fixes. The goal is reliability parity across the full target browser/OS matrix on a stock StitchLabOS Beta2 image, both in AP mode and on a regular LAN.

A local code review (2026-05-08) revealed that several of the most impactful root causes were not in the original frontend WebSocket layer at all, but in **routing** (`config.json` direct-port bypass of nginx), **fork-only daemons** (`live_jogd` polling Moonraker at ~30 req/s and auto-connecting a second WebSocket from every page load), and **dashboard rendering** (full-file embroidery G-code parsed on the main thread for a preview that only needs a finished-design thumbnail positioned in the selected hoop). Those findings are integrated into the cause tables and priority list below.

---

## Possible Causes (categorised)

### A. Frontend — `mainsail/src/plugins/webSocketClient.ts` and stores

| # | Issue | Evidence | Affects |
|---|-------|----------|---------|
| A1 | Main-thread `setInterval(10s)` keepalive paused by Chromium intensive throttling in backgrounded tabs (≥1 call/min after ~5 min hidden) → server `ping_timeout` closes socket. | [webSocketClient.ts:258-264](mainsail/src/plugins/webSocketClient.ts#L258-L264) | Chrome/Edge/Brave/Vivaldi (Win/Linux/Mac), less so Firefox; not Safari. |
| A2 | Heartbeat watchdog kills connection on **any 30 s gap in incoming messages** ([webSocketClient.ts:247-256](mainsail/src/plugins/webSocketClient.ts#L247-L256)). Slower Windows/Linux laptops with higher RTT or transient WiFi jitter trip it. Also: keepalive itself emits `server.info` every 10 s — naive "reset on emit" would let outbound traffic mask a dead server forever. | Hard 30 s timeout regardless of network. | All clients with jitter; worst on Windows WiFi laptops. |
| A3 | No `visibilitychange` / `online` / `offline` / `pageshow` handlers. Tab refocus or network change does not trigger an immediate reconnect — user waits for the next backoff tick (up to 30 s). | grep returns nothing in plugins/store. | All Chromium browsers, OS suspend/resume, VPN toggles. |
| A4 | `onerror → close()` is silent ([webSocketClient.ts:128-130](mainsail/src/plugins/webSocketClient.ts#L128-L130)). No `console.warn` / no telemetry. Diagnosing remote machines is blind. | Code review. | All. |
| A5 | `emit()` silently drops messages when `readyState !== OPEN` ([webSocketClient.ts:168-190](mainsail/src/plugins/webSocketClient.ts#L168-L190)). During reconnect, init-phase requests vanish; init list never empties → "Initializing…" forever. | Code review; matches the "long init" symptom. | Any client that reconnects mid-init. |
| A6 | `reconnects` counter resets only on `onopen`, not after sustained healthy traffic. Once it hits 5+, every future reconnect waits 32 s. | Code review. | Long-running tabs with intermittent drops. |
| A7 | `maxReconnects` field exists ([webSocketClient.ts:9](mainsail/src/plugins/webSocketClient.ts#L9)) but is unused — dead code. | Code review. | Cosmetic / future-bug risk. |
| A8 | No timeout on init requests dispatched from `socket/onOpen`. A single hung response stalls `initializationList` → `guiIsReady` never flips. | [src/store/server/actions.ts](mainsail/src/store/server/actions.ts), socket store. | All. |
| A9 | Heavy parallel init storm: `server.history.list` (100 items), recursive `server.files.get_directory` walk over all root dirs, `server.config`, `machine.system_info`, `machine.proc_stats`, `server.database.list`, etc. — all fired in parallel during `socket/onOpen`. On 2.4 GHz AP with one slow client this serialises into seconds. | [src/store/files/actions.ts](mainsail/src/store/files/actions.ts), [src/store/server/history/actions.ts](mainsail/src/store/server/history/actions.ts). | Slower clients; AP mode. |
| A10 | Heartbeat watchdog calls `socket.close()` from the timer; browsers may then report a clean close, and the current reconnect path does not reconnect clean closes — a heartbeat timeout can become a permanent disconnection dialog instead of recovery. | Code review. | All. |
| A11 | Dashboard embroidery preview fetches the **full active G-code file** and parses/renders stitch paths on the browser main thread, even though the UI only needs a thumbnail of the finished embroidery and its placement in the selected hoop. Stock Mainsail only shows thumbnails. Large files stall JS timers, so client keepalive/heartbeat code fires late and surfaces as "connection instability". Large `moveOffsets` / `stitchPointMoveIndices` arrays also bloat Vuex. | StitchLab embroidery dashboard component + Vuex store. | All clients with a large active embroidery job. |

### B. Browser & OS specific

| # | Issue | Affects |
|---|-------|---------|
| B1 | Chrome/Edge **Memory Saver** (default-on since Chrome 108) suspends backgrounded tabs entirely after a few minutes; the WebSocket dies, no JS runs to detect it until refocus. | Chrome/Edge on Windows/Linux/Mac. |
| B2 | Windows default TCP keepalive is **2 hours**; the OS won't notice a half-open WiFi-NIC-parked TCP connection until then. Combined with A2, the socket can be quietly half-open. Server-side `SO_KEEPALIVE` on nginx/Moonraker would help here. | Windows. |
| B3 | Client-side WiFi NIC power save (Intel AX2xx, Realtek RTL88xx common in Windows laptops) parks the radio aggressively. Pi-side `wlan0-powersave-off.service` does not help here. | Windows/Linux laptops on AP. |
| B4 | Windows **HTTPS-First Mode** in Edge/Chrome auto-upgrades `http://stitchlab.local` to `https://`, which fails (no cert). | Windows Edge/Chrome. |
| B5 | Linux distros frequently ship without `nss-mdns` enabled; `stitchlab.local` doesn't resolve at all. Firewalld blocks multicast on `external`/`public` zone. | Linux. |
| B6 | Windows `.local` resolution depends on Bonjour-Print-Services or LLMNR. Without it, only `.lan` or raw IP works. | Windows. |
| B7 | Corporate AV / VPN clients (Cisco AnyConnect, Zscaler, etc.) intercept HTTP and break WebSocket Upgrade handshakes. | Managed Windows laptops. |
| B8 | Cached Mainsail **service worker / PWA install** holds an old `config.json` and never updates because the SW caches itself with `StaleWhileRevalidate`. | All Chromium browsers, especially those that previously visited a different IP. |

### C. Server / image — nginx, Moonraker, AP

| # | Issue | Location |
|---|-------|----------|
| C1 | Production `mainsail/public/config.json` sets `"port": 7125` (upstream is `null`). Browser opens `ws://<host>:7125/websocket` directly, bypassing nginx entirely. Nginx `/websocket` hardening is therefore irrelevant for the main UI socket until same-origin routing is restored. Also weaker for HTTPS-first browsers, proxies, mobile clients, corporate firewalls, and PWA-cached config. | [mainsail/public/config.json](mainsail/public/config.json) |
| C2 | nginx WebSocket location is missing `proxy_send_timeout`, `tcp_nodelay`, and upstream `keepalive_timeout`. Defaults (60 s send, Nagle on) hurt slow/lossy links. No server-side `SO_KEEPALIVE` either. | [stitchlabos/image/src/modules/mainsail/filesystem/etc/nginx/sites-available/mainsail](stitchlabos/image/src/modules/mainsail/filesystem/etc/nginx/sites-available/mainsail) |
| C3 | nginx `gzip on` + `gzip_proxied any` compresses every dynamic API response, adding CPU + latency. Pi 4 fine; Pi Zero / older variants struggle. | same file |
| C4 | Moonraker ping config is patched directly into `application.py` via `sed` in [start_chroot_script](stitchlabos/image/src/modules/stitchlabos/start_chroot_script). Any update via `update_manager` reverts to upstream defaults (10 s / ~25 s) → reconnect loop returns silently after a software update. **Recheck:** current Moonraker exposes `websocket_ping_interval` as a native config key — `sed`-patching may no longer be necessary at all. | image-build script + runtime drift. |
| C5 | `live_jogd` runs by default with `STATUS_INTERVAL_S = 0.100` and three separate Moonraker HTTP queries per tick → **~30 req/s** to Moonraker before any user interaction. Competes with Mainsail init, Moonraker WebSocket ping/pong, file/history calls. Delayed WS replies surface as browser instability. | [live_jogd/config.py](live_jogd/config.py), [live_jogd/moonraker_client.py](live_jogd/moonraker_client.py) |
| C6 | `live_jogd` exposed WebSocket `:7150` and `mainsail/src/plugins/controllerWebSocket.ts` auto-connected from every loaded UI on mount of `TheControllerMenu`, even without a dongle. Same direct-port weaknesses as C1, no nginx in front, no TLS — same-origin HTTPS deployments will fail. Reconnect noise is independent of Moonraker health. At review time, stale comments/docs also still described the server as "not implemented"; those references have since been updated. | [mainsail/src/plugins/controllerWebSocket.ts](mainsail/src/plugins/controllerWebSocket.ts), [mainsail/src/components/TheControllerMenu.vue](mainsail/src/components/TheControllerMenu.vue) |
| C7 | AP profile uses default 1500 MTU. Clients tunnelled through VPN (smaller MTU) silently drop large WebSocket frames. | AccessPopup profile. |
| C8 | brcmfmac AP regulatory domain may default conservatively; reduces TX power → thin AP signal at desk distance. | image-build defaults. |
| C9 | `wlan0-powersave-off.service` is `After=klipper.service` (correct) but has no retry or watchdog if `iw` fails on a particular kernel. | systemd unit. |
| C10 | WiFi Manager startup RPCs are fork-only and call custom Moonraker endpoints backed by `nmcli`/scan behavior. Slow scans should not block Mainsail readiness or pile onto first-load reconnect pressure. | WiFi Manager Moonraker component. |
| C11 | Future G-Code intake/thumbnail generation can become a new stability problem if it scans all `gcodes/` at boot, runs multiple render jobs in parallel, blocks `guiIsReady`, or performs thumbnail generation synchronously from the dashboard. | StitchLab G-Code Intake service; see [G-Code Intake Stable Job Preview Plan.md](Reports&Plans/G-Code%20Intake%20Stable%20Job%20Preview%20Plan.md). |

---

## Recommended Fixes — Prioritised

> **Working order is the numbered sequence below.** Earlier items unblock later items: until P0-1 ships, P0-7 (nginx hardening) cannot affect the main UI socket; until P0-2/P0-3 ship, frontend WebSocket fixes are chasing symptoms of server-side overload.

### P0 — Must ship (highest impact, ~6–11 h total)

**P0-1. Restore same-origin Mainsail routing.** ~1 h.
- Set `mainsail/public/config.json` `"port": null` (upstream default). Keep `VUE_APP_PORT=7125` only in `.env.development.local` for local dev.
- Add a one-time image/update migration that rewrites `/home/pi/mainsail/config.json` when it still contains the legacy StitchLab default (`hostname: null`, `port: 7125`, `instancesDB: "moonraker"`), preserving user-customised remote/multi-printer configs.
- After deployment, verify both the served and PWA-cached config: DevTools network, hard refresh, fresh private window. Service worker uses `StaleWhileRevalidate`.
- Update docs that imply direct `:7125` is "stock" Mainsail UI access. Document `:7125` as Moonraker API access for tools/scripts; document browser UI access as same-origin `http://<host>/` and `ws://<host>/websocket`.
- File: [mainsail/public/config.json](mainsail/public/config.json), image-build migration.
- Mitigates C1. **Required before P0-7 has any effect on the main UI socket.**

**P0-2. Make `live_jogd` installed-but-inactive at runtime.** ~2–3 h.
- **Current symptom (verified 2026-05-10):** the unit is `systemctl enable`d in [start_chroot_script:32](stitchlabos/image/src/modules/live-jogd/start_chroot_script#L32) with `Restart=always` + `WantedBy=multi-user.target` and an `ExecStartPre` that waits 30 s for `/dev/stitchlab-dongle` ([live_jogd.service:12](stitchlabos/image/src/modules/live-jogd/filesystem/etc/systemd/system/live_jogd.service#L12)). On every Pi booted **without** a dongle, the unit fails after 30 s, then respawns every 3 s indefinitely → continuous journald spam and systemd churn, not just one-time boot churn. With dongle present, the daemon polls Moonraker at ~30 req/s baseline (three GETs × 10 Hz status loop in [live_jogd.py:672-685](stitchlabos/image/src/modules/live-jogd/filesystem/home/pi/live_jogd/live_jogd.py#L672-L685)) regardless of whether the user is actively driving the machine via controller.
- Ship the daemon, systemd unit, udev rule, and Controller-menu UI in every StitchLab build, but do not start `live_jogd` automatically. Remove `WantedBy=multi-user.target`; switch `Restart=always` → `Restart=on-failure` with a burst limit; do not `systemctl enable` in the install script. Activation is user-triggered through the Controller menu.
- Replace the topbar-mounted WebSocket auto-connect with an explicit Controller-menu action: user connects dongle → clicks **Initialize Dongle** / **Connect Controller** → Mainsail starts `live_jogd` via Moonraker service control → waits for service/WS readiness → connects to `:7150`. The service-control RPCs (`machine.services.start/stop/restart { service: "live_jogd" }`) are **already wired** in [TheControllerMenu.vue:360-382](mainsail/src/components/TheControllerMenu.vue#L360-L382) — the work is decoupling the WS auto-connect from `mounted()` ([TheControllerMenu.vue:262](mainsail/src/components/TheControllerMenu.vue#L262)) and making the user-triggered lifecycle reliable.
- **Verify Moonraker service-control allow list.** `machine.services.start/stop/restart` only operates on services Moonraker has been told it may control. Current Moonraker authorizes extra services through `<data_folder>/moonraker.asvc`; add/verify a `live_jogd` entry there for deployed images. Only if the deployed Moonraker version still uses legacy config, add `live_jogd` to `[machine] allowed_services` or the equivalent version-specific key. Without this, the UI buttons will fail even though the systemd unit exists.
- Stability UI scope: service stopped shows an explicit initialization action; service running shows dongle/peer status and pairing controls; this batch does **not** require controller-type labels, foot-pedal behavior, or a new motion-enabled Live Control mode.
- Stop/disable path closes the controller WebSocket, cancels frontend reconnect timers in [controllerWebSocket.ts](mainsail/src/plugins/controllerWebSocket.ts), resets the singleton state, calls `machine.services.stop`, releases `/dev/stitchlab-dongle`. Mainsail returns to pure normal operation with no `:7150` traffic.
- Update stale comments/docs that claimed the WS server was unimplemented: [types.ts:9-12](mainsail/src/store/server/controller/types.ts#L9-L12), [docs/05-configuration.md:13](docs/05-configuration.md#L13). The server has been implemented for some time ([live_jogd.py:317-444](stitchlabos/image/src/modules/live-jogd/filesystem/home/pi/live_jogd/live_jogd.py#L317-L444)).
- Files: [stitchlabos/image/src/modules/live-jogd/start_chroot_script](stitchlabos/image/src/modules/live-jogd/start_chroot_script), [stitchlabos/image/src/modules/live-jogd/filesystem/etc/systemd/system/live_jogd.service](stitchlabos/image/src/modules/live-jogd/filesystem/etc/systemd/system/live_jogd.service), [stitchlabos/image/src/modules/stitchlabos/filesystem/usr/local/bin/stitchlab-moonraker-service-control-patch](stitchlabos/image/src/modules/stitchlabos/filesystem/usr/local/bin/stitchlab-moonraker-service-control-patch), [stitchlab-moonraker-service-control-patch.service](stitchlabos/image/src/modules/stitchlabos/filesystem/etc/systemd/system/stitchlab-moonraker-service-control-patch.service), [mainsail/src/components/TheControllerMenu.vue](mainsail/src/components/TheControllerMenu.vue), [mainsail/src/plugins/controllerWebSocket.ts](mainsail/src/plugins/controllerWebSocket.ts), [mainsail/src/store/server/controller/actions.ts](mainsail/src/store/server/controller/actions.ts), Moonraker `<data_folder>/moonraker.asvc`.
- Mitigates C5, C6. **Removes ~30 req/s of background load from Moonraker AND the systemd restart loop on dongle-less Pis — this alone may resolve much of the "browser instability" symptom.**

**Live-jog/controller architecture split.** Controller types, Live Control semantics, foot-pedal/gamepad behavior, and firmware protocol changes are intentionally out of scope for this stability batch. Track and sharpen them separately in [Live Jogd Controller Architecture Plan.md](Live%20Jogd%20Controller%20Architecture%20Plan.md).

**P0-3. Reduce `live_jogd` Moonraker load when active.** ~2–3 h.
- Preferred: open one Moonraker WebSocket from `live_jogd` and subscribe to `toolhead` and `print_stats` via `printer.objects.subscribe`. Cache `notify_status_update`; keep sending serial status frames from cache.
- Low-risk immediate alternative: collapse the three polling calls per tick to one combined `GET /printer/objects/query?toolhead&print_stats` (cuts ~30/s → ~10/s without architecture change).
- Adaptive cadence: 1–2 Hz when no controller frames are arriving and deadman is not pressed; 10 Hz only while a controller is active or movement is possible.
- Verification: compare Moonraker CPU, request latency, WS close reasons, and first-dashboard-render time with `live_jogd` enabled vs disabled.
- File: [live_jogd/moonraker_client.py](live_jogd/moonraker_client.py), [live_jogd/config.py](live_jogd/config.py).
- Mitigates C5.

**P0-4. Stop dashboard live G-Code preview work; consume stable job-preview artifacts.** ~1–2 h.
- Remove the Status Panel dependency on full active G-Code fetch/parse. The dashboard must not call `/server/files/gcodes/<active-file>` just to draw a preview.
- Replace `EmbroideryPreview.vue` stitch-path rendering with a stable job-preview consumer: final intake thumbnail when available, existing `current_file.thumbnails` fallback, then a lightweight hoop/filename placeholder. Do **not** fall back to browser-side full-file parsing.
- Do **not** render stitch path, stitch order, travel moves, or stitch-by-stitch animation in the dashboard. The dashboard preview surface is only: selected hoop/usable area, finished-design thumbnail if available, placement summary, filename/progress.
- Remove dashboard dependencies on large `moveOffsets` / `stitchPointMoveIndices` arrays. `PrintstatusEmbroidery.vue` should use intake/file metadata for stitch count when available and Moonraker progress as fallback.
- This mitigates the connection-stability issue immediately even before the full Intake service exists: missing thumbnails produce a placeholder, not main-thread G-Code work.
- File: StitchLab dashboard preview/status components + corresponding Vuex metadata path.
- Mitigates A11.

**P0-4a. Keep G-Code Intake as the source of future thumbnails, with stability guardrails.** Coordination item; full implementation is tracked separately in [G-Code Intake Stable Job Preview Plan.md](Reports&Plans/G-Code%20Intake%20Stable%20Job%20Preview%20Plan.md).
- The new Intake plan defines the long-term answer: every stickable file gets a compatibility check plus cached thumbnail; upload creates an analysis/design thumbnail, start/prepare finalises the selected hoop/placement thumbnail.
- For this Cross-Platform Stability batch, the requirement is narrower: unfinished or missing Intake artifacts must never cause the dashboard to parse full G-Code, block first render, or join `guiIsReady`.
- If any Intake service ships in the same batch, it must be async, low priority, one worker at a time, no boot-time full scan, no synchronous dashboard generation, and cached by file hash + placement. Upload may enqueue analysis; only explicit Start/Prepare may wait for a missing check.
- Mainsail should consume Intake output through `current_file.thumbnails` if Moonraker can expose sidecar thumbnails there; otherwise through a small `stitchlab_intake` metadata API. In both cases the dashboard fetches only PNG/JSON, never the active `.gcode`.
- Mitigates A11 and prevents the new Intake service from becoming C11.

**P0-5. Visibility / online / offline awareness in the WebSocket client.** ~30 min.
- File: [mainsail/src/plugins/webSocketClient.ts](mainsail/src/plugins/webSocketClient.ts).
- On `document.visibilitychange → visible`: if `readyState !== OPEN`, force immediate reconnect (skip backoff); if OPEN, send `server.info` and reset heartbeat receive-side timestamp.
- On `window.online`: same — force reconnect if not OPEN.
- On `window.offline`: stop keepalive timers, mark socket as paused.
- Mitigates A1, A3, B1.

**P0-6. Heartbeat watchdog: separate send and receive timestamps.** ~20 min.
- File: same.
- Maintain `lastReceivedAt` (any inbound message **or** notification) **and** `lastSentAt` separately. Watchdog fires only on receive-side gap. Outbound keepalive does **not** reset the receive watchdog — otherwise a dead server is masked forever.
- Alternative: have keepalive use `emitAndWait('server.info')` with a timeout and reconnect on missing response.
- When the watchdog fires, set an explicit `heartbeatClose` reason on the socket and **schedule reconnect intentionally** — do not rely on `onclose` behavior, because client-initiated closes are reported as clean and the current reconnect path skips clean closes.
- Mitigates A2, A10.

**P0-7. Reset `reconnects` counter after sustained healthy traffic.** ~10 min.
- File: same. Store `lastOpenedAt`; on each `onmessage`, if `Date.now() - lastOpenedAt > 60_000 && reconnects > 0`, set `reconnects = 0`.
- Mitigates A6.

**P0-8. Lifecycle logging via module-scoped `log()` helper.** ~15 min.
- Per [mainsail/CLAUDE.md](mainsail/CLAUDE.md) (`[WebSocket]` prefix). Log: connect attempt, opened, error, close (with `code`/`reason`/`wasClean`), reconnect scheduled (`delay` ms), heartbeat fired, keepalive paused due to offline.
- Without this, remote-machine diagnosis is impossible.
- Mitigates A4.

**P0-9. Init-phase request timeout, reissue on reconnect, degraded-state tracking.** ~1 h.
- Files: [mainsail/src/store/socket/actions.ts](mainsail/src/store/socket/actions.ts) and `webSocketClient.ts`.
- Tag init waits with a 30 s timeout. On timeout: log, mark the component **failed** (degraded state — not silently removed), retry after reconnect/refocus. Only auto-suppress non-critical init modules so `guiIsReady` can flip; critical modules show diagnostics rather than a partially initialised UI with stale data.
- On reconnect during init, re-dispatch outstanding init modules instead of letting lost requests fall on the floor (A5).
- Mitigates A5, A8.

**P0-10. nginx WebSocket hardening + server-side TCP keepalive.** ~20 min.
- File: [stitchlabos/image/src/modules/mainsail/filesystem/etc/nginx/sites-available/mainsail](stitchlabos/image/src/modules/mainsail/filesystem/etc/nginx/sites-available/mainsail), `location /websocket`.
- Add: `proxy_send_timeout 86400;`, `tcp_nodelay on;`, `proxy_buffering off;`, and `proxy_socket_keepalive on;` (Linux uses system `tcp_keepalive_time` — drop it to ~120 s in `/etc/sysctl.d/`). This is what protects against half-open sockets on Windows clients (B2), which a JS-side fix alone cannot do.
- Optional: turn off gzip for `application/json` if Pi CPU is a concern (C3).
- Only effective once P0-1 routes the main UI through nginx.
- Mitigates C2, B2.

**P0-11. Make Moonraker ping override update-proof — or remove it.** ~30 min.
- **First check:** confirm whether the running Moonraker version exposes `websocket_ping_interval` / `websocket_ping_timeout` as native config keys in `[server]` or `[websocket]`. If yes, drop the `sed`-patch entirely and ship the values in `moonraker.conf` — this is the correct fix and removes update-drift risk by construction.
- Only if native config is unavailable: install a `moonraker.conf.d/websocket.cfg` snippet plus a post-update hook (`/etc/systemd/system/moonraker.service.d/`) that reapplies the patch idempotently, and add an `update_manager` exclusion entry.
- Files: [stitchlabos-config/moonraker/](stitchlabos-config/moonraker/), [stitchlabos/image/src/modules/stitchlabos/start_chroot_script](stitchlabos/image/src/modules/stitchlabos/start_chroot_script).
- Mitigates C4.

### P1 — Strong improvements (medium effort, ~5–7 h)

**P1-1. Migrate WebSocket to a Dedicated Web Worker.** ~4–6 h, exactly as scoped in [docs/proposals/websocket-worker-isolation.md](docs/proposals/websocket-worker-isolation.md).
- Removes background-tab throttling for Chromium clients (the lion's share of Win/Linux pain). Already designed; trigger condition matches current cross-platform reports.
- Note: do not use this to mask server-side overload from `live_jogd` (P0-3), dashboard stitch-path rendering that should be replaced by stable job-preview artifacts (P0-4), or an unbounded future G-Code Intake service (C11/P0-4a); it must come *after* those.
- Mitigates A1 fully, B1 fully, partially B2 (worker-side keepalive keeps JS pinging; server-side `SO_KEEPALIVE` from P0-10 is what closes the half-open hole).

**P1-2. Light-weight init: defer non-critical fetches.** ~1–2 h.
- Files: [mainsail/src/store/server/history/actions.ts](mainsail/src/store/server/history/actions.ts), [mainsail/src/store/files/actions.ts](mainsail/src/store/files/actions.ts).
- History first page = 25 (not 100). Don't recursively walk the whole `gcodes/` tree at boot — fetch top level only, lazy-fetch on directory open. `guiIsReady` should depend only on the modules required to render the dashboard.
- Future G-Code Intake status/thumbnail metadata must follow the same rule: lazy, cache-backed, and never required for initial Mainsail readiness.
- General guideline: avoid storing large arrays in Vuex unless they back reactive UI.
- Mitigates A9.

**P1-3. Diagnostic debug overlay.** ~1 h.
- Toggleable (`?debug` query param): show socket state, last close code, reconnects, heartbeat-due-in, keepalive-due-in, init list contents, last failed init module.
- Lets a Windows user report "connection closed with code 1006 every 90 s" without F12.
- Doubles as the data source for the verification gate (P1-3 supersedes log-grep for tests 2/3 below).
- Mitigates A4 from the user side.

**P1-4. AP-mode docs for non-Mac clients.** ~30 min.
- Add Issue 6 to [docs/runbooks/ap-troubleshooting.md](docs/runbooks/ap-troubleshooting.md): Windows steps (disable HTTPS-first for `192.168.50.5`, install Bonjour Print Services or use `stitchlab.lan`/IP, disable WiFi NIC power save in adapter properties); Linux steps (install `libnss-mdns`, allow mDNS in firewalld).
- Mitigates B3, B4, B5, B6.

**P1-5. Keep WiFi Manager startup non-critical.** ~30 min.
- Add timeouts on `nmcli`/scan endpoints; never block Mainsail readiness on them; don't put scans or AP reconfiguration into the first-load critical path.
- Mitigates C10.

### P2 — Nice-to-have (only if symptoms persist)

- **P2-1.** Service-worker / PWA cache busting — emit a cache-bust version number into `config.json` and check on load (B8).
- **P2-2.** AP MTU tuning + WiFi country code in the image (`wpa_supplicant.conf` `country=` and AP profile `802-11-wireless.mtu`) (C7, C8).
- **P2-3.** Watchdog wrapper around `wlan0-powersave-off.service` (`Restart=on-failure` with limit) (C9).
- **P2-4.** Proxy `live_jogd` through nginx (`/controller/websocket -> 127.0.0.1:7150`) and have the frontend connect same-origin. Right answer if always-live controller status is required or HTTPS is planned. Defer until after P0-2 establishes the user-gated lifecycle.
- **P2-5.** SharedWorker fallback if multi-tab usage becomes common (already evaluated and rejected — keep deferred unless seen in the wild).

---

## Critical Files

| File | Change Set |
|------|-----------|
| [mainsail/public/config.json](mainsail/public/config.json) | P0-1 |
| Image-build migration for `/home/pi/mainsail/config.json` | P0-1 |
| [stitchlabos/image/src/modules/live-jogd/start_chroot_script](stitchlabos/image/src/modules/live-jogd/start_chroot_script) | P0-2 |
| [stitchlabos/image/src/modules/live-jogd/filesystem/etc/systemd/system/live_jogd.service](stitchlabos/image/src/modules/live-jogd/filesystem/etc/systemd/system/live_jogd.service) | P0-2 |
| [mainsail/src/components/TheControllerMenu.vue](mainsail/src/components/TheControllerMenu.vue) | P0-2 |
| [mainsail/src/plugins/controllerWebSocket.ts](mainsail/src/plugins/controllerWebSocket.ts) | P0-2 |
| [mainsail/src/store/server/controller/actions.ts](mainsail/src/store/server/controller/actions.ts) | P0-2 |
| Moonraker service allow-list (`<data_folder>/moonraker.asvc`; legacy deployed versions may use `[machine] allowed_services`) | P0-2 |
| [stitchlabos/image/src/modules/stitchlabos/filesystem/usr/local/bin/stitchlab-moonraker-service-control-patch](stitchlabos/image/src/modules/stitchlabos/filesystem/usr/local/bin/stitchlab-moonraker-service-control-patch), [stitchlab-moonraker-service-control-patch.service](stitchlabos/image/src/modules/stitchlabos/filesystem/etc/systemd/system/stitchlab-moonraker-service-control-patch.service) | P0-2 |
| [mainsail/src/store/server/controller/types.ts](mainsail/src/store/server/controller/types.ts), [docs/05-configuration.md](docs/05-configuration.md) (controller WebSocket docs/status references) | P0-2 |
| [stitchlabos/image/src/modules/live-jogd/filesystem/home/pi/live_jogd/live_jogd.py](stitchlabos/image/src/modules/live-jogd/filesystem/home/pi/live_jogd/live_jogd.py) | P0-3 |
| [stitchlabos/image/src/modules/live-jogd/filesystem/home/pi/live_jogd/config.py](stitchlabos/image/src/modules/live-jogd/filesystem/home/pi/live_jogd/config.py) | P0-3 |
| [stitchlabos/image/src/modules/live-jogd/filesystem/home/pi/live_jogd/moonraker_client.py](stitchlabos/image/src/modules/live-jogd/filesystem/home/pi/live_jogd/moonraker_client.py) | P0-3 |
| StitchLab dashboard stable job-preview/status components + Vuex metadata path | P0-4 |
| [Reports&Plans/G-Code Intake Stable Job Preview Plan.md](Reports&Plans/G-Code%20Intake%20Stable%20Job%20Preview%20Plan.md), future `stitchlab-gcode-intake` CLI + Moonraker `stitchlab_intake` component | P0-4a / separate Intake track |
| [mainsail/src/plugins/webSocketClient.ts](mainsail/src/plugins/webSocketClient.ts) | P0-5, P0-6, P0-7, P0-8 |
| [mainsail/src/store/socket/actions.ts](mainsail/src/store/socket/actions.ts) | P0-9 |
| [stitchlabos/image/src/modules/mainsail/filesystem/etc/nginx/sites-available/mainsail](stitchlabos/image/src/modules/mainsail/filesystem/etc/nginx/sites-available/mainsail) | P0-10 |
| `/etc/sysctl.d/` (TCP keepalive) | P0-10 |
| [stitchlabos-config/moonraker/](stitchlabos-config/moonraker/), [stitchlabos/image/src/modules/stitchlabos/start_chroot_script](stitchlabos/image/src/modules/stitchlabos/start_chroot_script) | P0-11 |
| [mainsail/src/plugins/webSocketWorker.ts](mainsail/src/plugins/webSocketWorker.ts) (new), [mainsail/src/plugins/webSocketTypes.ts](mainsail/src/plugins/webSocketTypes.ts) (new) | P1-1 |
| [mainsail/src/store/server/history/actions.ts](mainsail/src/store/server/history/actions.ts), [mainsail/src/store/files/actions.ts](mainsail/src/store/files/actions.ts) | P1-2 |
| [docs/runbooks/ap-troubleshooting.md](docs/runbooks/ap-troubleshooting.md) | P1-4 |

---

## Verification

**Bench setup.** Pi 4 in AP mode (Stitchlab SSID), three clients in parallel:
1. **Mac (Safari + Firefox)** — must remain stable; regression check.
2. **Windows 11 laptop (Edge + Firefox)** — primary regression target.
3. **Linux desktop (Chromium + Firefox)** — secondary target.

**Tests per client:**
1. **Cold load**: open `http://192.168.50.5`, time to first dashboard render. Target <5 s on Win/Linux (currently >10 s).
2. **30-min foreground soak**: tab in foreground, idle. Tail `~/printer_data/logs/moonraker.log | grep -iE 'websocket|ping'` **and** the P1-3 debug overlay. Expect zero `ping timed out` closes and zero reconnects in the overlay.
3. **30-min backgrounded soak**: tab hidden behind another window. Same checks. After P1-1, expect zero clean reconnects on Chromium.
4. **Network blip recovery**: `iw dev wlan0 disconnect` on the client for 5 s, reassociate. Mainsail UI should reconnect within <2 s of network restore (P0-5, P0-7).
5. **Tab refocus**: leave hidden 10 min, refocus. Expect immediate reconnect, no 30 s wait (P0-5).
6. **Init under reconnect**: pull power on the AP for 1 s during initial load. UI should reissue init requests rather than hang on "Initializing…" forever; failed critical modules should show diagnostics rather than a stale partial UI (P0-9).
7. **Routing verification**: with DevTools network open, confirm the main UI WebSocket goes to `ws://<host>/websocket` (same-origin, through nginx), **not** `ws://<host>:7125/websocket`. Verify both freshly-cleared cache and PWA-cached state (P0-1).
8. **Moonraker upgrade resilience**: `sudo /home/pi/moonraker/scripts/install-moonraker.sh -f` (or update via update_manager), confirm `websocket_ping_interval=30` is still in effect afterward (P0-11).
9. **Controller inactive baseline**: boot with no dongle and load Mainsail. Confirm `live_jogd` is stopped, no `:7150` WebSocket is opened, and the Controller menu shows an explicit initialization action instead of reconnect noise (P0-2). Confirm Moonraker request rate at idle is at upstream baseline (no ~30 req/s background load).
10. **Controller user flow**: connect dongle, click Controller-menu initialization, confirm `live_jogd` starts, `:7150` connects only after service/WS readiness, and pairing/status controls work (P0-2). Verify `machine.services.start { service: "live_jogd" }` actually succeeds — i.e. `live_jogd` is present in Moonraker's service allow-list (`<data_folder>/moonraker.asvc` on current Moonraker, legacy `allowed_services` only if required by the deployed version) and the inactive-static-unit service-control patch is active when the deployed Moonraker needs it.
11. **Return to normal use**: stop/disconnect the controller service from the menu. Confirm the WebSocket closes cleanly, reconnect timers stop, `/dev/stitchlab-dongle` is released, no further `:7150` traffic appears in DevTools, and Mainsail remains connected to Moonraker (P0-2).
12. **Dongle-less Pi sanity**: boot a Pi with no dongle ever attached. After 5 minutes, `journalctl -u live_jogd` should show **zero** restart attempts (unit not enabled, or `Restart=on-failure` burst limit honored — no 3-second respawn loop) (P0-2).
13. **Large embroidery preview**: load a >5 MB embroidery G-code as the active job and watch the dashboard. The dashboard should fetch only a thumbnail/placement JSON when available, or show a lightweight placeholder when not available. DevTools must show no full active `.gcode` download from the Status Panel and no browser-side parser load for the dashboard. Main thread should not block; keepalive/heartbeat in the debug overlay should fire on schedule; no "instability" symptom should appear from the preview alone (P0-4).
14. **G-Code Intake guardrail**: if the new Intake service is present, upload or select several large G-code files while three clients are connected. Intake jobs should run one at a time, low priority, without joining `guiIsReady`, without boot-time full-tree scan, and without causing Moonraker request latency or WebSocket reconnects. Start/Prepare may wait for a missing check; dashboard render may not (P0-4a/C11).

**Acceptance gate.** All fourteen tests pass on all three clients before declaring this batch done. P1-1 (worker) is required for tests 2 & 3 to pass on Chromium under sustained background throttling. Controller-type detection, per-type motion behavior, foot-pedal behavior, and firmware protocol changes are tracked in the separate Live Jogd Controller Architecture plan and are not required for this stability batch.

---

## Out of scope

- Replacing the Vue 2 stack or Vuex 3 store. (Guideline: avoid storing large arrays in Vuex regardless — see P0-4, P1-2.)
- Server-side Moonraker rewrite (we're on stock + a single ping override, and P0-11 may even remove that).
- Fixing Mainsail upstream — these are all StitchLab-side patches; if any prove generally useful, they can be upstreamed PR-by-PR later.

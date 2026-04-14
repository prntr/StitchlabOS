# Proposal: Isolate Moonraker WebSocket in a Dedicated Web Worker

> **Status:** Not implemented. Scoped for a future release candidate if connection reliability across diverse browsers/devices becomes a priority, or if similar reconnect symptoms reappear on customer systems beyond the ones covered by the Beta2 three-layer fix ([runbooks/ap-troubleshooting.md](runbooks/ap-troubleshooting.md#issue-5-frontend-websocket-reconnects-in-ap-mode)).
>
> **Current state (Beta2):** WebSocket runs on the main thread with a 10 s app-level keepalive. Stable in the foreground; backgrounded Chromium tabs occasionally reconnect because Chrome throttles `setInterval` in hidden tabs (intensive throttling, ~1 call/min after ~5 min). Safari is unaffected because it doesn't throttle as aggressively. Reconnects are clean (<1 s) and transparent — not a bug per se, just visible wear.

---

## Motivation

The Beta2 fix relies on a main-thread keepalive running every 10 s. If the browser ever stops firing that timer on schedule — backgrounded tab, browser under memory pressure, an ill-behaved addon, OS-level throttling on low-power devices — the Moonraker server sees no pong within its configured timeout and closes the socket. We then reconnect, but the user briefly sees "Connecting…".

This is a universal browser reality, not something we can fully solve server-side without making Moonraker tolerate minute-long gaps (which would also delay detection of genuinely dead clients). The robust answer is to move the keepalive — and ideally the WebSocket itself — off the main thread into a context that browsers do not throttle.

---

## Options Evaluated

### Option A — Dedicated Web Worker (recommended for RC)

Run the WebSocket client inside a per-tab Web Worker. Main thread communicates via `postMessage`.

**Pros:**
- Supported in every browser we care about (IE10+, all Safari versions, Firefox, Chrome, Edge, iOS Safari).
- Workers are not subject to main-thread `setInterval` throttling. Chrome's intensive throttling *does* reach workers in long-hidden tabs (~5 min hidden) but remains far more permissive than main-thread throttling.
- Straightforward migration path from the current [webSocketClient.ts](../mainsail/src/plugins/webSocketClient.ts).
- No cross-tab coordination required.

**Cons:**
- Serialization overhead for every message (negligible for Mainsail's message volume).
- Worker needs its own build entry (Vite handles this via `?worker` imports).
- Message passing doubles the surface area for bugs (every `emit`/response must cross the worker boundary).

**Residual gap:** if the user has multiple Mainsail tabs open and all are backgrounded for a long period, each tab's worker is independently throttleable. Acceptable for the workshop use case (typically one tab open).

### Option B — SharedWorker

Single worker shared by all tabs on the same origin. One WebSocket, many consumers.

**Pros:**
- One active tab keeps the worker alive for all tabs.
- Single WebSocket reduces Moonraker's connection count (relevant only for multi-tab users).

**Cons:**
- **Safari removed SharedWorker in 2012, reintroduced in Safari 16 (Sept 2022).** Safari 15 and earlier, iOS Safari ≤15: no SharedWorker. For a product targeting "as many browsers as possible," this is disqualifying unless we combine it with a Dedicated Worker fallback — doubling implementation cost.
- Cross-tab message bus is fiddly (port lifecycle, cleanup when tabs close).
- Worth the complexity only if multi-tab scenarios are common. They aren't.

### Option C — Service Worker

Intercepts network requests. Possible to run a keepalive, but Service Workers are optimized for offline caching, not long-lived WebSockets, and have aggressive lifecycle management (browser can terminate them at any time).

**Not recommended.** Fights the primitive.

### Option D — Page Visibility API alone (no worker)

Detect when the tab regains focus and force a reconnect. Doesn't prevent the disconnect, just speeds up recovery.

**Worth adding alongside the worker**, not as a replacement. See [Additional Improvements](#additional-improvements) below.

---

## Recommended Scope — Option A (Dedicated Web Worker)

### Target Behavior

- WebSocket connection lifecycle (connect, close, reconnect, keepalive, heartbeat) runs entirely in a Dedicated Worker.
- Main thread (Vuex, Vue components) speaks to the worker over a typed `postMessage` protocol. The existing `$socket.emit`/`emitAndWait` API stays unchanged from the callers' perspective.
- Worker survives main-thread stalls (heavy Vuex commits, ECharts render spikes, CodeMirror tokenizer on large gcode files).
- Worker is not subject to main-thread `setInterval` throttling, so the 10 s keepalive is reliable whether or not the tab is in the foreground.

### Architecture

```
┌────────────── Main thread (UI) ─────────────┐
│  Vue components / Vuex store / $socket proxy │
│                                              │
│  emit(method, params)       ──postMessage──▶ │
│  on message from store      ◀──postMessage── │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────── Dedicated Worker ───────────────┐
│  WebSocket instance                          │
│  Waits / promise resolution                  │
│  Keepalive (setInterval 10 s)                │
│  Heartbeat (silence watchdog)                │
│  Reconnect with exp backoff                  │
└──────────────────────────────────────────────┘
```

### Public API (unchanged for callers)

Keep the existing `WebSocketClient` surface as a **thin proxy** on the main thread:
- `emit(method, params, options)` → forward to worker, fire-and-forget on the UI side.
- `emitAndWait(method, params, options)` → forward to worker, resolve the promise when the worker posts back the matching result.
- `emitBatch(messages)` → forward array.
- `connect()` / `close()` → control messages to the worker.

Everything currently importing `$socket` keeps working.

### Message Protocol (worker ↔ main)

| Direction | Type | Payload |
|-----------|------|---------|
| main → worker | `connect` | `{ url }` |
| main → worker | `close` | `{}` |
| main → worker | `emit` | `{ id, method, params, options }` |
| main → worker | `emitAndWait` | `{ id, method, params, options }` |
| main → worker | `emitBatch` | `{ messages: [...] }` |
| worker → main | `opened` | `{}` |
| worker → main | `closed` | `{ code, reason, wasClean }` |
| worker → main | `message` | `{ data }` — unsolicited server push for `socket/onMessage` dispatch |
| worker → main | `result` | `{ id, result }` — resolves a pending `emitAndWait` |
| worker → main | `error` | `{ id, error }` — rejects a pending `emitAndWait` |
| worker → main | `loading-start` / `loading-end` | `{ name }` — drives the existing `socket/addLoading` dispatches |

All IDs are main-thread-allocated so the main-thread proxy can resolve promises without needing worker-side state to cross the boundary.

### Files Touched

| File | Change |
|------|--------|
| `mainsail/src/plugins/webSocketClient.ts` | Thin proxy; no timers, no WebSocket instance — just postMessage wiring |
| `mainsail/src/plugins/webSocketWorker.ts` | **New.** Owns WebSocket, waits list, keepalive, heartbeat, reconnect |
| `mainsail/src/plugins/webSocketTypes.ts` | **New.** Message protocol types shared by both sides |
| `mainsail/vite.config.ts` | Verify worker import works (`?worker` suffix; Vite handles out of the box) |
| `mainsail/src/store/socket/actions.ts` | Unchanged; receives dispatches the same way |

### Estimated Effort

- Extraction + protocol plumbing: **2–3 h**
- Testing (foreground stability, backgrounded tab over 30 min, tab switch storm, Safari/Chrome/Firefox matrix, mobile Safari): **1–2 h**
- Edge cases (worker crash recovery, page reload mid-reconnect, multi-instance farm mode): **1 h**

Total: **~4–6 hours** for a conservative implementation.

### Risks

1. **Worker crash or errored state.** Mitigation: on `worker.onerror`, respawn the worker and reconnect. Cheap.
2. **Mobile Safari background tab suspension.** iOS Safari fully suspends backgrounded tabs after ~30 s — workers included. Not fixable from JS; when the user refocuses, Vue mounts and the worker respawns. Acceptable.
3. **Farm mode** (`/src/store/farm/`) uses the same plugin — ensure the worker instance is per farm socket, not a singleton, or refactor to accept a URL per connect call.
4. **TypeScript**: worker file must not import Vue/Vuex (those depend on `window`). Keep `webSocketWorker.ts` dependency-free except for the protocol types.

### Verification Plan

1. **Stability test:** open Mainsail in Chrome, switch to another app for 30+ min, return. Moonraker log should show zero `ping timed out` closes during that window.
2. **Browser matrix:** repeat on Safari, Firefox, Chromium incognito, iOS Safari, Android Chrome.
3. **Farm mode:** verify multi-printer switching still works if the lab uses it.
4. **Moonraker log:** session-long `tail -f | grep websocket` should show one `Websocket Opened` per browser open and subsequent opens only on genuine network events (not timer throttling).

### Rollback

Worker isolation is additive and the public API is unchanged. If a regression surfaces, revert the two new files and restore the inline implementation in `webSocketClient.ts` from git. No server-side or image changes coupled to this.

---

## Additional Improvements (complement, not replace)

These are cheap wins that strengthen resilience regardless of whether we ship the worker:

- **Page Visibility API**: on `visibilitychange` → `visible`, if the socket is closed or stale (no traffic in N seconds), force an immediate reconnect instead of waiting for the backoff timer. Covers the "user comes back to the tab" case gracefully.
- **`online`/`offline` events**: on `online`, trigger a reconnect. Useful for laptops that suspend/resume or change networks.
- **Reset backoff on successful message exchange**, not just on `onopen`: a socket that opens but receives no data for 60 s is effectively dead.

Estimated effort: ~30 min combined. Worth doing alongside the worker, or standalone if the worker is postponed.

---

## When to Implement

Pull this off the shelf if any of these surface:

- Customer reports of Mainsail "disconnecting" on mobile devices or specific laptop models that aren't reproduced in our Pi 4 / Mac test setup.
- A browser update tightens timer throttling further (it has only gotten stricter over time).
- RC-level reliability goals that want "zero visible reconnects under any reasonable condition."
- Support burden from Beta2 customers that maps to this pattern in Moonraker logs (`ping timed out` with mostly healthy network otherwise).

If none of the above, the Beta2 three-layer fix is good enough to ship.

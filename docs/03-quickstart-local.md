# Quickstart (Local)

Goal: run the UI against a local Moonraker/Klipper simulator.

## 1) Start the simulator

From `virtual-klipper-printer/`:

```bash
docker compose up -d
```

Expected endpoints:
- Moonraker: `http://localhost:7125`
- Dummy webcam: `http://localhost:8110/?action=stream`

## 2) Start the UI

From `mainsail/`:

```bash
npm install
npm run serve
```

Expected endpoint:
- Vite dev server: `http://localhost:8080`

## 3) Point UI at the simulator

The UI reads default connection info from `mainsail/public/config.json`.
If you change it and don’t see changes, be aware the PWA/service worker can cache aggressively.

## 4) Verify

```bash
curl http://localhost:7125/printer/info
```

UI should show connecting + then ready.

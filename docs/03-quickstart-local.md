# Quickstart (Local)

> Run UI against local Moonraker/Klipper simulator.

## 1. Start simulator

```bash
cd virtual-klipper-printer
docker compose up -d
```

## 2. Start UI

```bash
cd mainsail
npm install
npm run serve
```

## 3. Verify

```bash
curl http://localhost:7125/printer/info
```

Open `http://localhost:8080` - UI should connect.

See [05-configuration.md](05-configuration.md) for all ports and endpoints.

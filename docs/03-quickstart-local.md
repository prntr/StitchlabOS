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

## 4. (Optional) Connect an AI agent via WebMCP

In dev mode, Mainsail loads [WebMCP](https://webmcp.dev) automatically — a blue widget appears in the bottom-right corner.

```bash
# Install the WebMCP bridge (one time)
cd MCP/webmcp && npm install
```

Configure your MCP client (Claude Desktop, Cursor, Codex, etc.):

```json
{
  "mcpServers": {
    "webmcp": {
      "command": "npx",
      "args": ["-y", "@jason.today/webmcp@latest", "--mcp"]
    }
  }
}
```

Then:
1. Ask your AI agent to generate a WebMCP token
2. Paste the token into the blue widget in Mainsail
3. The agent can now read printer state, send G-code, query config, and more

See [MCP/webmcp/README.md](../MCP/webmcp/README.md) for available tools and detailed setup.

See [05-configuration.md](05-configuration.md) for all ports and endpoints.

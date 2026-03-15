# Component: TurtleStitch (Offline)

## Scope

This page documents the StitchLAB integration and runtime context only.
For TurtleStitch / Snap! development guidance, use the upstream docs in `turtlestitch/docs/`.

## Current status (dev Pi)

- Nginx serves TurtleStitch from `/home/pi/turtlestitch` on `http://stitchlabdev.local:3000/`.
- `/etc/nginx/sites-available/turtlestitch` is enabled via `/etc/nginx/sites-enabled/`.
- `turtlestitch.service` exists but is disabled/inactive to avoid a port `3000` conflict.

## Entry points

- Direct: `http://<pi-host>:3000/`
- Mainsail nav link: `VITE_TURTLESTITCH_URL` if set, else `http://<current-host>:3000`
  (`mainsail/src/components/mixins/navigation.ts`).

## Development guidance (short)

- Prefer upstream extension APIs before editing `turtlestitch/src/`.
- Read in this order:
  - `turtlestitch/docs/README.md` (overview + paths to the right docs)
  - `turtlestitch/docs/Extensions.md` (new blocks, menus, palettes, JS loaders)
  - `turtlestitch/docs/API.md` (embedding / integration)
  - `turtlestitch/docs/CONTRIBUTING.md` (style + JSLint rules)

## Verification on the Pi

```bash
curl -I http://localhost:3000
ss -ltnp | grep ':3000'
systemctl status turtlestitch.service
```

## Project File Management

TurtleStitch's standard offline mode only saves projects as downloads to the browser's local computer. This integration adds the ability to save and load project XML files directly on the Pi using Moonraker's file API.

### Storage Location

```
/home/pi/printer_data/gcodes/turtlestitch_projects/
```

Projects are stored as XML files in a subdirectory of the `gcodes` root, making them:
- Included in printer_data backups
- Accessible via Moonraker's file API
- Visible in Mainsail's file browser

### Moonraker API Endpoints

**Upload project:**
```bash
curl -F 'file=@myproject.xml' \
     -F 'root=gcodes' \
     -F 'path=turtlestitch_projects' \
     'http://localhost:7125/server/files/upload'
```

**List projects:**
```bash
# List files in turtlestitch_projects subdirectory
curl 'http://localhost:7125/server/files/directory?path=gcodes/turtlestitch_projects' | \
  jq '.result.files'
```

**Download project:**
```bash
curl 'http://localhost:7125/server/files/gcodes/turtlestitch_projects/myproject.xml'
```

**Delete project:**
```bash
curl -X DELETE 'http://localhost:7125/server/files/gcodes/turtlestitch_projects/myproject.xml'
```

### JavaScript Integration Example

```javascript
const moonrakerURL = `http://${window.location.hostname}:7125`;

// Save to Pi
async function saveProjectToPi(projectName, projectXML) {
  const blob = new Blob([projectXML], { type: 'application/xml' });
  const formData = new FormData();
  formData.append('file', blob, projectName + '.xml');
  formData.append('root', 'gcodes');
  formData.append('path', 'turtlestitch_projects');
  
  const response = await fetch(`${moonrakerURL}/server/files/upload`, {
    method: 'POST',
    body: formData
  });
  return await response.json();
}

// Load from Pi
async function loadProjectFromPi(projectPath) {
  const response = await fetch(
    `${moonrakerURL}/server/files/gcodes/${projectPath}`
  );
  return await response.text();
}

// List projects
async function listPiProjects() {
  const response = await fetch(
    `${moonrakerURL}/server/files/directory?path=gcodes/turtlestitch_projects`
  );
  const data = await response.json();
  return data.result.files; // Array of {filename, modified, size, permissions}
}
```

### UI Integration Status

| Feature | Status | Notes |
|---------|--------|-------|
| Moonraker API | ✅ Done | File operations working |
| Pi directory | ✅ Done | Auto-created on first save |
| TurtleStitch "Save to Pi" button | ✅ Done | StitchLAB source with file icon |
| TurtleStitch "Load from Pi" browser | ✅ Done | Full project list with preview |
| Moonraker auto-detection | ✅ Done | Button only appears if Moonraker available |
| Delete from Pi | ✅ Done | Works from project dialog |
| TurtleStitch cloud via Pi | ⏸️ Planned | Needs nginx reverse proxy + `snap-cloud-domain` update |

**Location:** Modified `turtlestitch/src/gui.js`

**How to use:**
1. Open TurtleStitch (http://stitchlabdev.local:3000)
2. Click **File → Save As...**
3. Click the **StitchLAB** button (file icon)
4. Enter project name and click **Save**
5. To load: **File → Open** → click **StitchLAB** → select project

See [05-configuration.md](../05-configuration.md#turtlestitch-project-file-management) for additional API details and examples.

### Future Work

- Proxy upstream TurtleStitch cloud through nginx on the Pi (e.g. `/turtlestitch-cloud/`) to allow cloud login/save with same-origin cookies; requires updating the `snap-cloud-domain` meta in `turtlestitch/index.html` once the proxy exists.

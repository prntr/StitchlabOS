# Processing Integration Guide

> Summary for Processing users who want to interact with StitchLabOS / StitchLAB from a Processing sketch.

## Overview

Processing should usually talk to StitchLab through Moonraker, the same API layer used by the Mainsail frontend. Moonraker exposes both HTTP and WebSocket APIs for printer status, G-code execution, file upload, and print control.

There is also a custom `live_jogd` WebSocket used for the wireless StitchLab controller/dongle. That socket is useful for controller status, pairing, WiFi, and LED control, but it is not the primary printer control API. The daemon is installed but not auto-started; port `7150` only exists after the Controller menu or Moonraker service-control starts `live_jogd`.

## Network Interfaces

| Purpose | URL | Protocol | Use From Processing |
|---|---|---|---|
| Printer commands and status | `http://stitchlab.local:7125` | Moonraker HTTP | Easiest for one-shot commands and polling |
| Live printer status and JSON-RPC | `ws://stitchlab.local:7125/websocket` | Moonraker WebSocket | Best for real-time status and frontend-like behavior |
| Controller/dongle status | `ws://stitchlab.local:7150` | Custom `live_jogd` WebSocket | Use only after `live_jogd` is started; dongle/controller state and settings only |
| Mainsail UI | `http://stitchlab.local` | Browser UI | Human control/debugging |
| TurtleStitch, if enabled | `http://stitchlab.local:3000` | Static web app | Design generation workflow |

If `.local` name resolution is unavailable, use the device IP address instead, for example `http://192.168.50.5:7125`.

## Recommended Approach

For most Processing sketches:

1. Generate geometry, stitch paths, or G-code in Processing.
2. Send direct commands with Moonraker HTTP `POST /printer/gcode/script`.
3. Query status with Moonraker HTTP `GET /printer/objects/query?...`.
4. Use the Moonraker WebSocket only when you need continuous live state.
5. Avoid direct serial access to `/dev/stitchlab-dongle` while `live_jogd` is running.

## Processing APIs You Can Use

Processing has built-in helpers for simple HTTP reads:

- `loadJSONObject(url)` for JSON status endpoints
- `loadStrings(url)` for text endpoints

For HTTP `POST`, multipart file upload, and WebSockets, use Java classes from Processing or install a Processing WebSocket/HTTP library.

References:

- Processing `loadJSONObject()`: https://processing.org/reference/loadjsonobject_
- Processing `loadStrings()`: https://processing.org/reference/loadstrings_
- Processing Serial library: https://processing.org/reference/libraries/serial/
- Moonraker printer API: https://moonraker.readthedocs.io/en/latest/external_api/printer/
- Moonraker file API: https://moonraker.readthedocs.io/en/latest/external_api/file_manager/

## Sending G-code Over HTTP

Moonraker endpoint:

```text
POST http://stitchlab.local:7125/printer/gcode/script
Content-Type: application/json

{"script":"STITCH"}
```

Minimal Processing helper:

```java
import java.net.*;
import java.io.*;

String STITCHLAB = "http://stitchlab.local:7125";

void sendGcode(String script) {
  try {
    URL url = new URL(STITCHLAB + "/printer/gcode/script");
    HttpURLConnection c = (HttpURLConnection) url.openConnection();
    c.setRequestMethod("POST");
    c.setRequestProperty("Content-Type", "application/json");
    c.setDoOutput(true);

    String body = "{\"script\":\"" + jsonEscape(script) + "\"}";
    OutputStream os = c.getOutputStream();
    os.write(body.getBytes("UTF-8"));
    os.close();

    println("G-code HTTP " + c.getResponseCode());
    c.disconnect();
  } catch (Exception e) {
    e.printStackTrace();
  }
}

String jsonEscape(String s) {
  return s
    .replace("\\", "\\\\")
    .replace("\"", "\\\"")
    .replace("\n", "\\n")
    .replace("\r", "");
}
```

Example commands:

```java
sendGcode("STITCH");
sendGcode("NEEDLE_TOGGLE");
sendGcode("LOCK_STITCH COUNT=3");
sendGcode("EMBROIDERY_STATUS");
sendGcode("G91\nG1 X1.0 Y0 F1200\nG90");
```

Use the emergency stop endpoint for emergency stops instead of queueing `M112`:

```text
POST http://stitchlab.local:7125/printer/emergency_stop
```

## Querying Printer Status

Simple Processing status query:

```java
JSONObject result = loadJSONObject(
  "http://stitchlab.local:7125/printer/objects/query?toolhead&print_stats&gcode_move"
);

JSONObject status = result.getJSONObject("result").getJSONObject("status");
println(status);
```

Useful Moonraker objects:

| Object | Meaning |
|---|---|
| `toolhead` | Position, homed axes, velocity limits |
| `gcode_move` | G-code coordinate state |
| `print_stats` | Current job state and filename |
| `display_status` | Print progress |
| `configfile` | Loaded Klipper config |
| `save_variables` | Persistent macro variables, if configured |
| `gcode_button gantry_detect` | Gantry attached/detached state, if configured |
| `as5600 e0_encoder` | Needle angle/status, if encoder module is deployed |

Example query for mode and gantry state, once mode switching is configured:

```text
GET /printer/objects/query?save_variables&gcode_button%20gantry_detect
```

Example query for encoder state, once the AS5600 module is deployed:

```text
GET /printer/objects/query?as5600%20e0_encoder
```

## Moonraker WebSocket

This is the WebSocket used by the StitchLabOS/Mainsail frontend:

```text
ws://stitchlab.local:7125/websocket
```

It uses JSON-RPC 2.0. A command looks like this:

```json
{
  "jsonrpc": "2.0",
  "method": "printer.gcode.script",
  "params": {
    "script": "STITCH"
  },
  "id": 1
}
```

Subscribe to live printer object updates:

```json
{
  "jsonrpc": "2.0",
  "method": "printer.objects.subscribe",
  "params": {
    "objects": {
      "toolhead": null,
      "print_stats": null,
      "gcode_move": null
    }
  },
  "id": 2
}
```

Moonraker then pushes messages like:

```json
{
  "jsonrpc": "2.0",
  "method": "notify_status_update",
  "params": [
    {
      "toolhead": {
        "position": [0, 0, 0, 0]
      }
    },
    12345.67
  ]
}
```

The Mainsail implementation is in `mainsail/src/plugins/webSocketClient.ts`.

## `live_jogd` WebSocket

The custom controller/dongle WebSocket is separate:

```text
ws://stitchlab.local:7150
```

If the port is closed, start the service from the Mainsail Controller menu or through Moonraker `machine.services.start { service: "live_jogd" }`.

It does not use JSON-RPC. It uses plain JSON messages with a `type` field.

Request status:

```json
{"type":"get_status"}
```

Possible commands:

```json
{"type":"wifi","value":"on"}
{"type":"wifi","value":"off"}
{"type":"pairing","value":"on"}
{"type":"pairing","value":"off"}
{"type":"select_controller","value":0}
{"type":"led","value":128}
{"type":"clear_peers"}
```

Typical status response:

```json
{
  "type": "status",
  "dongle_connected": true,
  "dongle_info": {
    "mac": "",
    "firmware_version": "1.0.0",
    "wifi_enabled": true,
    "controller_count": 0,
    "led_brightness": 128
  },
  "dongle_status": {
    "uptime_seconds": 0,
    "packets_rx": 0,
    "packets_tx": 0,
    "crc_errors": 0,
    "link_active": false,
    "pairing_mode": false,
    "rssi": -50
  },
  "peers": [],
  "joystick": {
    "vx": 0,
    "vy": 0,
    "deadman": false,
    "buttons": 0
  }
}
```

Use this socket when your Processing sketch needs to display controller/dongle state. Use Moonraker for actual printer control.

## StitchLab Macros

The current StitchLabOS embroidery macros include:

| Macro | Purpose |
|---|---|
| `STITCH` | One complete stitch cycle, modeled as 5 mm Z movement |
| `LOCK_STITCH COUNT=3` | Multiple stitches in place |
| `NEEDLE_TOGGLE` | Toggle needle between UP and DOWN for maintenance |
| `NEEDLE_ADJUST AMOUNT=0.1` | Fine Z/needle adjustment |
| `ZERO_NEEDLE_POSITION` | Move to needle UP and set logical Z to 0 |
| `EMBROIDERY_HOME` | Home XY and Z, then move to center |
| `EMBROIDERY_STATUS` | Print current embroidery status to console |

The important machine model is:

```text
1 full handwheel rotation = 5 mm Z travel = 1 complete stitch
Needle UP   = Z modulo 5 mm near 0
Needle DOWN = Z modulo 5 mm near 2.5
```

## G-code Generation From Processing

Processing can generate regular Klipper G-code. For embroidery previews in the StitchLabOS UI, these conventions are useful:

```gcode
(STITCH_COUNT:123)
; color r:255 g:0 b:0
G90
G1 X10.0 Y10.0 F1200
G1 Z5.0 F600
G1 X20.0 Y10.0 F1200
G1 Z10.0 F600
```

Notes:

- `G0` / `G1` moves with `X` or `Y` form the path preview.
- Z-only moves are interpreted as stitch points by the preview parser.
- Color comments in the form `; color r:<0-255> g:<0-255> b:<0-255>` create color changes in the preview.
- `STITCH_COUNT` in parentheses can provide an explicit stitch count.

## Uploading and Starting Files

Moonraker uploads use multipart form data:

```text
POST /server/files/upload
Content-Type: multipart/form-data
field: file
optional field: root=gcodes
optional field: path=<subdirectory>
```

Start an uploaded file:

```text
POST /printer/print/start?filename=your_file.gcode
```

For quick experiments, sending generated G-code directly with `printer/gcode/script` is simpler. For full embroidery jobs, upload the file and start it through Moonraker.

## Direct Serial Access

Direct serial communication with the dongle is possible in theory through Processing's Serial library, but it is usually the wrong layer.

The dongle serial device is:

```text
/dev/stitchlab-dongle
115200 baud
```

The binary protocol is framed as:

```text
[0xAA][TYPE][LEN][PAYLOAD...][CRC16_LE][0x55]
```

Avoid opening this port from Processing while `live_jogd` is running, because `live_jogd` owns the serial link and bridges it to Moonraker and WebSocket APIs.

## Safety

- Prefer Moonraker's `/printer/emergency_stop` endpoint for emergency stop behavior.
- Do not send XY moves in sewing mode when the gantry is detached.
- Check `toolhead.homed_axes` before XY movement.
- Treat documented mode-switching and foot-pedal features as conditional until they are deployed in the active Klipper config.
- Keep movement commands small while testing from Processing.
- Use Mainsail's console and `EMBROIDERY_STATUS` to verify state while developing sketches.

## Current Implementation Notes

- Moonraker WebSocket is the main frontend WebSocket: `ws://<host>:7125/websocket`.
- `live_jogd` WebSocket is custom and separate: `ws://<host>:7150`, and only listens while the user-triggered service is active.
- Foot pedal support is documented but not currently implemented in the checked `live_jogd` code.
- Mode switching macros are documented in `MODE_SWITCHING.md`, but the active macro file currently contains the embroidery control macros only.
- Encoder support is documented under `docs/encoder/` and depends on deploying `as5600.py` into Klipper and adding the matching config.

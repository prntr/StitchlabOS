"""
live_jogd Configuration
"""

# Serial connection to ESP32-C3 Dongle
SERIAL_PORT = "/dev/stitchlab-dongle"
SERIAL_BAUD = 115200
SERIAL_TIMEOUT = 0.1  # seconds
DONGLE_REQUEST_TIMEOUT_S = 2.0  # Wait for a query/command response frame

# Moonraker API
MOONRAKER_HOST = "localhost"
MOONRAKER_PORT = 7125

# Jogging parameters
MAX_VELOCITY_MM_S = 200.0     # Maximum allowed velocity
JOG_INTERVAL_S = 0.020        # 20ms between G-code commands (50 Hz)
STATUS_INTERVAL_S = 0.100     # 100ms between status updates while a
                              # controller is active (10 Hz). When no
                              # controller is sending frames and deadman
                              # is not pressed, the status loop falls
                              # back to STATUS_INTERVAL_IDLE_S to keep
                              # baseline Moonraker load close to zero.
STATUS_INTERVAL_IDLE_S = 1.0  # 1 Hz when no controller is active.
CONTROLLER_ACTIVE_TIMEOUT_S = 1.0  # No controller frame in this window
                                   # -> drop to idle cadence.

# Z-axis step size (for button-based Z movement)
Z_STEP_MM = 0.1
Z_FEEDRATE = 600  # mm/min

# Safety
DEADMAN_REQUIRED = True       # Require deadman button for X/Y movement
REQUIRE_HOMED = True          # Only allow jogging when homed
LINK_TIMEOUT_S = 0.200        # Emergency stop if no frame for 200ms
LIVE_CONTROL_LINK_TIMEOUT_S = 2.0
# Link gaps above LINK_TIMEOUT_S immediately zero motion and block movement.
# Only a sustained gap disables the explicit Live Control gate. Normal ESP-NOW
# jitter can exceed 200ms briefly, so using LINK_TIMEOUT_S for both made the
# UI switch turn itself off during otherwise valid controller use.

# Controller type policy. Unknown controllers stay status-only until a
# firmware type, config mapping, or explicit UI label identifies them.
CONTROLLER_TYPE_UNKNOWN = "unknown"
CONTROLLER_TYPE_GAMEPAD = "gamepad"
CONTROLLER_TYPE_FOOT_PEDAL = "foot_pedal"
VALID_CONTROLLER_TYPES = (
    CONTROLLER_TYPE_UNKNOWN,
    CONTROLLER_TYPE_GAMEPAD,
    CONTROLLER_TYPE_FOOT_PEDAL,
)

# Optional runtime classification for old firmware that does not report a
# controller type. Keys are uppercase MACs ("AA:BB:CC:DD:EE:FF") or OUIs
# ("AA:BB:CC"). Values must be one of VALID_CONTROLLER_TYPES.
CONTROLLER_TYPE_BY_MAC = {}
CONTROLLER_TYPE_BY_OUI = {}

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "/var/log/live_jogd.log"

# Button bit definitions (must match protocol.h)
BTN_A = 1 << 0       # Z+
BTN_B = 1 << 1       # Stitch
BTN_X = 1 << 2       # Home
BTN_Y = 1 << 3       # Z-
BTN_SELECT = 1 << 4  # E-Stop
BTN_START = 1 << 5   # Reserve

# UI Action codes (must match protocol.h)
UI_ACT_NONE = 0x00
UI_ACT_HOME_X = 0x01
UI_ACT_HOME_Y = 0x02
UI_ACT_HOME_Z = 0x03
UI_ACT_HOME_ALL = 0x04
UI_ACT_HOME_XY = 0x05
UI_ACT_STITCH = 0x06  # Single stitch
UI_ACT_MACRO = 0x20

# Macro IDs for UI_ACT_MACRO
MACRO_NEEDLE_TOGGLE = 0

# WebSocket server for Mainsail integration
WEBSOCKET_PORT = 7150

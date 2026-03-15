#!/usr/bin/env python3
"""
live_jogd - Live Jogging Daemon for Klipper

Receives joystick data from ESP32-C3 dongle via USB serial
and sends movement commands to Klipper via Moonraker API.
"""

import asyncio
import serial
import logging
import signal
import sys
import time
import json
from typing import Optional, Set

import websockets
from websockets.server import serve as ws_serve

from serial_protocol import (
    FrameParser, FrameBuilder, StatusFrame, JoystickFrame, HeartbeatFrame
)
from moonraker_client import MoonrakerClient
import config

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("live_jogd")

# Path to dongle_api.py
DONGLE_API_PATH = "/home/pi/live_jogd/dongle_api.py"


class LiveJogDaemon:
    """Main daemon class for live jogging control."""

    def __init__(self):
        self.serial_port: Optional[serial.Serial] = None
        self.moonraker = MoonrakerClient(
            host=config.MOONRAKER_HOST,
            port=config.MOONRAKER_PORT
        )
        self.parser = FrameParser()

        # State tracking
        self.running = False
        self.last_frame_time = 0.0
        self.last_jog_time = 0.0
        self.last_z_time = 0.0
        self.last_status_time = 0.0
        self.status_seq = 0

        # Current joystick state
        self.current_vx = 0.0
        self.current_vy = 0.0
        self.current_deadman = False
        self.current_buttons = 0
        self.prev_buttons = 0

        # Cached printer state
        self.homed_axes = ""
        self.printer_idle = True
        self.current_pos = (0.0, 0.0, 0.0)

        # Button state for edge detection
        self.button_pressed = {}

        # WebSocket clients
        self.ws_clients: Set[websockets.WebSocketServerProtocol] = set()

        # Dongle state for WebSocket
        self.dongle_connected = False
        self.dongle_info = {
            "mac": "",
            "firmware_version": "1.0.0",
            "wifi_enabled": True,
            "controller_count": 0,
            "led_brightness": 128
        }
        self.dongle_status = {
            "uptime_seconds": 0,
            "packets_rx": 0,
            "packets_tx": 0,
            "crc_errors": 0,
            "link_active": False,
            "pairing_mode": False,
            "rssi": -50
        }
        self.peers = []

    async def start(self):
        """Start the daemon."""
        logger.info("Starting live_jogd daemon...")

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown)

        self.running = True

        # Connect to Moonraker
        await self.moonraker.connect()
        logger.info(f"Connected to Moonraker at {config.MOONRAKER_HOST}:{config.MOONRAKER_PORT}")

        # Open serial port
        self._open_serial()
        self.dongle_connected = self.serial_port is not None and self.serial_port.is_open

        # Run main loops
        try:
            await asyncio.gather(
                self._serial_read_loop(),
                self._jog_loop(),
                self._status_loop(),
                self._watchdog_loop(),
                self._websocket_server(),
                self._ws_broadcast_loop(),
                self._dongle_query_loop(),
            )
        except asyncio.CancelledError:
            pass
        finally:
            await self._cleanup()

    def _shutdown(self):
        """Handle shutdown signal."""
        logger.info("Shutdown requested...")
        self.running = False

    async def _cleanup(self):
        """Cleanup resources."""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        await self.moonraker.close()
        # Close all WebSocket connections
        for ws in self.ws_clients:
            await ws.close()
        logger.info("Cleanup complete")

    def _open_serial(self):
        """Open serial port to dongle."""
        try:
            self.serial_port = serial.Serial(
                port=config.SERIAL_PORT,
                baudrate=config.SERIAL_BAUD,
                timeout=config.SERIAL_TIMEOUT
            )
            logger.info(f"Serial port {config.SERIAL_PORT} opened at {config.SERIAL_BAUD} baud")
        except serial.SerialException as e:
            logger.error(f"Failed to open serial port: {e}")
            raise

    # ==================== Dongle API Commands ====================

    async def _dongle_set_wifi(self, enabled: bool) -> bool:
        """Set WiFi state via dongle_api.py."""
        try:
            cmd = ['python3', DONGLE_API_PATH, '--wifi', 'on' if enabled else 'off']
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                self.dongle_info["wifi_enabled"] = enabled
                logger.info(f"WiFi set to {'on' if enabled else 'off'}")
                return True
            else:
                logger.error(f"WiFi command failed: {stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"WiFi command exception: {e}")
            return False

    async def _dongle_set_pairing(self, enabled: bool) -> bool:
        """Set pairing mode via dongle_api.py."""
        try:
            cmd = ['python3', DONGLE_API_PATH, '--pairing', 'on' if enabled else 'off']
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                self.dongle_status["pairing_mode"] = enabled
                logger.info(f"Pairing mode set to {'on' if enabled else 'off'}")
                return True
            else:
                logger.error(f"Pairing command failed: {stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"Pairing command exception: {e}")
            return False

    async def _dongle_set_led(self, brightness: int) -> bool:
        """Set LED brightness via dongle_api.py."""
        try:
            cmd = ['python3', DONGLE_API_PATH, '--led', str(brightness)]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                self.dongle_info["led_brightness"] = brightness
                logger.info(f"LED brightness set to {brightness}")
                return True
            else:
                logger.error(f"LED command failed: {stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"LED command exception: {e}")
            return False

    async def _dongle_clear_peers(self) -> bool:
        """Clear all peers via dongle_api.py."""
        try:
            cmd = ['python3', DONGLE_API_PATH, '--clear-peers']
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                self.peers = []
                logger.info("Peers cleared")
                return True
            else:
                logger.error(f"Clear peers command failed: {stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"Clear peers command exception: {e}")
            return False

    async def _dongle_select_controller(self, slot_id: int) -> bool:
        """Select active controller (local only for now)."""
        try:
            for peer in self.peers:
                peer["active"] = (peer["slot_id"] == slot_id)
            logger.info(f"Selected controller slot {slot_id}")
            return True
        except Exception as e:
            logger.error(f"Select controller exception: {e}")
            return False

    async def _dongle_query_loop(self):
        """Periodically query dongle for real status data."""
        while self.running:
            await asyncio.sleep(5)  # Query every 5 seconds
            if not self.dongle_connected:
                continue
            
            try:
                # Query info
                cmd = ['python3', DONGLE_API_PATH, '--query', 'info', '--json']
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode == 0 and stdout:
                    try:
                        info = json.loads(stdout.decode())
                        self.dongle_info.update(info)
                    except json.JSONDecodeError:
                        pass

                # Query status
                cmd = ['python3', DONGLE_API_PATH, '--query', 'status', '--json']
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode == 0 and stdout:
                    try:
                        status = json.loads(stdout.decode())
                        self.dongle_status.update(status)
                    except json.JSONDecodeError:
                        pass

                # Query peers
                cmd = ['python3', DONGLE_API_PATH, '--query', 'peers', '--json']
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode == 0 and stdout:
                    try:
                        peers = json.loads(stdout.decode())
                        if isinstance(peers, list):
                            self.peers = peers
                    except json.JSONDecodeError:
                        pass

            except Exception as e:
                logger.debug(f"Dongle query exception: {e}")

    # ==================== WebSocket Server ====================

    async def _websocket_server(self):
        """Run WebSocket server for Mainsail UI."""
        port = getattr(config, 'WEBSOCKET_PORT', 7150)
        logger.info(f"Starting WebSocket server on port {port}")

        async def handler(websocket):
            self.ws_clients.add(websocket)
            logger.info(f"WebSocket client connected. Total: {len(self.ws_clients)}")
            try:
                # Send initial status
                await self._ws_send_status(websocket)
                
                async for message in websocket:
                    await self._ws_handle_message(websocket, message)
            except websockets.ConnectionClosed:
                pass
            finally:
                self.ws_clients.discard(websocket)
                logger.info(f"WebSocket client disconnected. Total: {len(self.ws_clients)}")

        try:
            async with ws_serve(handler, "0.0.0.0", port):
                logger.info(f"WebSocket server listening on 0.0.0.0:{port}")
                while self.running:
                    await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")

    async def _ws_handle_message(self, websocket, message: str):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")
            
            if msg_type == "get_status":
                await self._ws_send_status(websocket)
            
            elif msg_type == "wifi":
                value = data.get("value", "off")
                success = await self._dongle_set_wifi(value == "on")
                await websocket.send(json.dumps({
                    "type": "command_response",
                    "command": "wifi",
                    "success": success
                }))
                if success:
                    await self._ws_broadcast_status()
            
            elif msg_type == "pairing":
                value = data.get("value", "off")
                success = await self._dongle_set_pairing(value == "on")
                await websocket.send(json.dumps({
                    "type": "command_response",
                    "command": "pairing",
                    "success": success
                }))
                if success:
                    await self._ws_broadcast_status()
            
            elif msg_type == "select_controller":
                slot_id = data.get("value", 0)
                success = await self._dongle_select_controller(slot_id)
                await websocket.send(json.dumps({
                    "type": "command_response",
                    "command": "select_controller",
                    "success": success
                }))
                if success:
                    await self._ws_broadcast_status()
            
            elif msg_type == "led":
                brightness = data.get("value", 128)
                success = await self._dongle_set_led(brightness)
                await websocket.send(json.dumps({
                    "type": "command_response",
                    "command": "led",
                    "success": success
                }))
            
            elif msg_type == "clear_peers":
                success = await self._dongle_clear_peers()
                await websocket.send(json.dumps({
                    "type": "command_response",
                    "command": "clear_peers",
                    "success": success
                }))
                if success:
                    await self._ws_broadcast_status()
            
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from WebSocket: {message}")
        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"WebSocket message error: {e}")

    async def _ws_send_status(self, websocket):
        """Send status to a specific WebSocket client."""
        status = self._build_ws_status()
        try:
            await websocket.send(json.dumps(status))
        except websockets.ConnectionClosed:
            pass

    async def _ws_broadcast_status(self):
        """Broadcast status to all WebSocket clients."""
        if not self.ws_clients:
            return
        
        status = self._build_ws_status()
        message = json.dumps(status)
        
        # Broadcast to all clients
        disconnected = set()
        for ws in self.ws_clients:
            try:
                await ws.send(message)
            except websockets.ConnectionClosed:
                disconnected.add(ws)
        
        # Remove disconnected clients
        self.ws_clients -= disconnected

    async def _ws_broadcast_loop(self):
        """Periodically broadcast status to all WebSocket clients."""
        while self.running:
            await self._ws_broadcast_status()
            await asyncio.sleep(1)  # Broadcast every second

    def _build_ws_status(self) -> dict:
        """Build status dict for WebSocket."""
        # Update dongle_status based on current state
        self.dongle_status["link_active"] = (
            time.monotonic() - self.last_frame_time < config.LINK_TIMEOUT_S
            if self.last_frame_time > 0 else False
        )
        
        # Check if we have an active controller
        has_active = any(p.get("active", False) for p in self.peers)
        if not has_active and self.last_frame_time > 0:
            # Auto-create a peer if we're receiving data
            if not self.peers:
                self.peers = [{
                    "slot_id": 0,
                    "mac": "AA:BB:CC:DD:EE:FF",
                    "active": True,
                    "last_seen": int(time.time()),
                    "packet_count": self.dongle_status.get("packets_rx", 0)
                }]
        
        return {
            "type": "status",
            "dongle_connected": self.dongle_connected,
            "dongle_info": self.dongle_info,
            "dongle_status": self.dongle_status,
            "peers": self.peers,
            "joystick": {
                "vx": self.current_vx,
                "vy": self.current_vy,
                "deadman": self.current_deadman,
                "buttons": self.current_buttons
            }
        }

    # ==================== Serial Communication ====================

    async def _serial_read_loop(self):
        """Read and parse serial data from dongle."""
        logger.info("Serial read loop started")

        while self.running:
            if not self.serial_port or not self.serial_port.is_open:
                await asyncio.sleep(1)
                continue

            try:
                # Read available data
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)

                    for byte in data:
                        frame = self.parser.feed(byte)
                        if frame:
                            await self._handle_frame(frame)
                else:
                    await asyncio.sleep(0.001)  # 1ms sleep when no data

            except serial.SerialException as e:
                logger.error(f"Serial read error: {e}")
                await asyncio.sleep(1)

    async def _handle_frame(self, frame):
        """Handle a parsed frame."""
        self.last_frame_time = time.monotonic()
        self.dongle_status["packets_rx"] = self.dongle_status.get("packets_rx", 0) + 1

        if isinstance(frame, JoystickFrame):
            await self._handle_joystick(frame)
        elif isinstance(frame, HeartbeatFrame):
            self._handle_heartbeat(frame)

    async def _handle_joystick(self, frame: JoystickFrame):
        """Process joystick frame."""
        # Update state
        self.current_vx = frame.velocity_x
        self.current_vy = frame.velocity_y
        self.current_deadman = frame.deadman
        self.prev_buttons = self.current_buttons
        self.current_buttons = frame.buttons

        # Handle UI actions from controller
        if frame.ui_action != 0:
            await self._handle_ui_action(frame.ui_action, frame.ui_value)
            # Avoid accidental button actions in the same frame.
            return

        # Handle button edges
        await self._handle_buttons(frame.buttons)

    async def _handle_ui_action(self, action: int, value: int):
        """Handle UI action from controller."""
        if action == config.UI_ACT_HOME_ALL:
            logger.info("UI Action: Home All")
            await self.moonraker.home("xyz")
        elif action == config.UI_ACT_HOME_XY:
            logger.info("UI Action: Home XY")
            await self.moonraker.home("xy")
        elif action == config.UI_ACT_HOME_X:
            logger.info("UI Action: Home X")
            await self.moonraker.home("x")
        elif action == config.UI_ACT_HOME_Y:
            logger.info("UI Action: Home Y")
            await self.moonraker.home("y")
        elif action == config.UI_ACT_HOME_Z:
            logger.info("UI Action: Home Z")
            await self.moonraker.home("z")
        elif action == config.UI_ACT_STITCH:
            logger.info("UI Action: Stitch")
            await self.moonraker.run_macro("STITCH")
        elif action == config.UI_ACT_MACRO:
            if value == config.MACRO_NEEDLE_TOGGLE:
                logger.info("UI Action: Needle Toggle")
                await self.moonraker.run_macro("NEEDLE_TOGGLE")
            else:
                logger.info("UI Action: Macro %d", value)

    async def _handle_buttons(self, buttons: int):
        """Handle button presses (edge detection)."""
        # Detect rising edges
        rising = buttons & ~self.prev_buttons

        # Button B: Stitch
        if rising & config.BTN_B:
            logger.info("Button B: STITCH")
            await self.moonraker.run_macro("STITCH")

        # Button X: Home
        if rising & config.BTN_X:
            logger.info("Button X: HOME XYZ")
            await self.moonraker.home("xyz")

        # Button SELECT: Emergency Stop
        if rising & config.BTN_SELECT:
            logger.warning("Button SELECT: EMERGENCY STOP")
            await self.moonraker.emergency_stop()

        # Button A/Y: Z movement (continuous while held)
        if buttons & config.BTN_A:
            await self._z_step(config.Z_STEP_MM)
        if buttons & config.BTN_Y:
            await self._z_step(-config.Z_STEP_MM)

    async def _z_step(self, step: float):
        """Move Z axis by step amount."""
        # Rate limit Z movement
        now = time.monotonic()
        if now - self.last_z_time < 0.1:  # Max 10 Hz for Z
            return

        if config.REQUIRE_HOMED and 'z' not in self.homed_axes:
            logger.warning("Z not homed, ignoring Z movement")
            return

        await self.moonraker.jog_relative(z=step, feedrate=config.Z_FEEDRATE)
        self.last_z_time = now

    def _handle_heartbeat(self, frame: HeartbeatFrame):
        """Process heartbeat frame."""
        self.dongle_status["uptime_seconds"] = frame.uptime_ms // 1000
        self.dongle_status["crc_errors"] = frame.crc_errors
        logger.debug(
            f"Heartbeat: uptime={frame.uptime_ms}ms, "
            f"rx={frame.packets_received}, fwd={frame.packets_forwarded}, "
            f"crc_err={frame.crc_errors}, link={frame.link_status}"
        )

    async def _jog_loop(self):
        """Send jog commands at fixed interval."""
        logger.info("Jog loop started")

        while self.running:
            now = time.monotonic()

            # Check if it's time to send a jog command
            if now - self.last_jog_time >= config.JOG_INTERVAL_S:
                self.last_jog_time = now

                # Only jog if conditions are met
                if await self._can_jog():
                    await self._send_jog()

            await asyncio.sleep(0.001)  # Small sleep for responsiveness

    async def _can_jog(self) -> bool:
        """Check if jogging is allowed."""
        # Require deadman for X/Y movement
        if config.DEADMAN_REQUIRED and not self.current_deadman:
            return False

        # Check if homed
        if config.REQUIRE_HOMED and not ('x' in self.homed_axes and 'y' in self.homed_axes):
            return False

        # Check if idle
        if not self.printer_idle:
            return False

        return True

    async def _send_jog(self):
        """Send jog command based on current velocity."""
        vx = self.current_vx
        vy = self.current_vy

        # Clamp velocity
        max_vel = config.MAX_VELOCITY_MM_S
        vx = max(-max_vel, min(max_vel, vx))
        vy = max(-max_vel, min(max_vel, vy))

        # Skip if no movement
        if abs(vx) < 0.1 and abs(vy) < 0.1:
            return

        # Calculate distance for this interval
        dt = config.JOG_INTERVAL_S
        dx = vx * dt
        dy = vy * dt

        # Calculate feedrate (mm/min)
        speed = max(abs(vx), abs(vy))
        feedrate = speed * 60

        # Send G-code
        await self.moonraker.jog_relative(x=dx, y=dy, feedrate=feedrate)

    async def _status_loop(self):
        """Send status updates to dongle and update cached state."""
        logger.info("Status loop started")

        while self.running:
            now = time.monotonic()

            if now - self.last_status_time >= config.STATUS_INTERVAL_S:
                self.last_status_time = now

                # Update cached state from Moonraker
                self.homed_axes = await self.moonraker.get_homed_axes()
                self.printer_idle = await self.moonraker.is_idle()
                self.current_pos = await self.moonraker.get_position()

                # Build and send status frame
                await self._send_status()

            await asyncio.sleep(0.01)

    async def _send_status(self):
        """Send status frame to dongle."""
        if not self.serial_port or not self.serial_port.is_open:
            return

        # Build flags
        flags = 0
        if 'x' in self.homed_axes:
            flags |= StatusFrame.HOMED_X
        if 'y' in self.homed_axes:
            flags |= StatusFrame.HOMED_Y
        if self.printer_idle:
            flags |= StatusFrame.IDLE
        else:
            flags |= StatusFrame.BUSY
        if self.moonraker.connected:
            flags |= StatusFrame.CONNECTED

        flags |= self._needle_state_flags(self.current_pos[2])

        # Position in micrometers
        pos_x_um = int(self.current_pos[0] * 1000)
        pos_y_um = int(self.current_pos[1] * 1000)

        frame = StatusFrame(
            seq=self.status_seq,
            pos_x=pos_x_um,
            pos_y=pos_y_um,
            flags=flags
        )
        self.status_seq = (self.status_seq + 1) & 0xFFFF

        # Send to serial
        self.dongle_status["packets_tx"] = self.dongle_status.get("packets_tx", 0) + 1
        try:
            data = FrameBuilder.build_status(frame)
            self.serial_port.write(data)
        except serial.SerialException as e:
            logger.error(f"Failed to send status: {e}")

    def _needle_state_flags(self, z_mm: float) -> int:
        """Infer needle up/down state from Z position."""
        remainder = z_mm % 5.0

        if remainder < 0.5 or remainder > 4.5:
            return StatusFrame.NEEDLE_UP
        if 1.5 < remainder < 3.5:
            return StatusFrame.NEEDLE_DOWN
        return 0

    async def _watchdog_loop(self):
        """Monitor link health and trigger emergency stop if needed."""
        logger.info("Watchdog loop started")

        while self.running:
            now = time.monotonic()

            # Check for link timeout
            if self.last_frame_time > 0:
                elapsed = now - self.last_frame_time
                if elapsed > config.LINK_TIMEOUT_S:
                    logger.warning(f"Link timeout! No frame for {elapsed:.3f}s")
                    # Reset velocity to stop movement
                    self.current_vx = 0
                    self.current_vy = 0
                    self.current_deadman = False

            await asyncio.sleep(0.05)  # Check every 50ms


async def main():
    """Main entry point."""
    daemon = LiveJogDaemon()
    await daemon.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

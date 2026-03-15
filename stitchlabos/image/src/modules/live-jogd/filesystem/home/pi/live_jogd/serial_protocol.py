"""
Serial Protocol Parser for StitchLabDongle

Binary framing protocol:
[START_0xAA][TYPE][LEN][PAYLOAD...][CRC16_LE][END_0x55]

With byte-stuffing for reserved bytes.
"""

import struct
from dataclasses import dataclass
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)

# Protocol constants (must match protocol.h)
START_BYTE = 0xAA
END_BYTE = 0x55
ESCAPE_BYTE = 0x5C
ESCAPE_XOR = 0x20

# Message types
MSG_TYPE_JOYSTICK = 0x01
MSG_TYPE_STATUS = 0x02
MSG_TYPE_HEARTBEAT = 0x03
MSG_TYPE_ACK = 0x04
MSG_TYPE_ERROR = 0x05
MSG_TYPE_JOYSTICK_EXT = 0x06
MSG_TYPE_COMMAND = 0x10
MSG_TYPE_QUERY = 0x11
MSG_TYPE_RESPONSE = 0x12

# Query/response IDs
QUERY_INFO = 0x01
QUERY_STATUS = 0x02
QUERY_PEERS = 0x03

# Command IDs
CMD_WIFI_ENABLE = 0x02
CMD_ENTER_PAIRING = 0x04
CMD_EXIT_PAIRING = 0x05
CMD_CLEAR_PEERS = 0x06
CMD_SAVE_CONFIG = 0x09

# Response status codes
RESP_OK = 0x00

# Frame sizes
JOYSTICK_FRAME_SIZE = 12  # Updated: seq(2) + vx(2) + vy(2) + deadman(1) + buttons(1) + ui_action(1) + ui_value(1) + crc(2)
JOYSTICK_EXT_SIZE = 13    # controller_id(1) + JoystickFrame(12)
STATUS_FRAME_SIZE = 13
HEARTBEAT_FRAME_SIZE = 19
DONGLE_INFO_SIZE = 14
DONGLE_STATUS_SIZE = 17
PEER_INFO_SIZE = 16

# CRC16-CCITT lookup table (nibble-based, 16 entries)
CRC16_TABLE = [
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7,
    0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF
]


def crc16_ccitt(data: bytes) -> int:
    """Calculate CRC16-CCITT over data bytes."""
    crc = 0xFFFF
    for byte in data:
        crc = ((crc << 4) ^ CRC16_TABLE[((crc >> 12) ^ (byte >> 4)) & 0x0F]) & 0xFFFF
        crc = ((crc << 4) ^ CRC16_TABLE[((crc >> 12) ^ byte) & 0x0F]) & 0xFFFF
    return crc


@dataclass
class JoystickFrame:
    """Joystick data from controller."""
    controller_id: int
    seq: int
    vx: int          # mm/s × 10
    vy: int          # mm/s × 10
    deadman: bool
    buttons: int
    ui_action: int
    ui_value: int

    @property
    def velocity_x(self) -> float:
        """X velocity in mm/s."""
        return self.vx / 10.0

    @property
    def velocity_y(self) -> float:
        """Y velocity in mm/s."""
        return self.vy / 10.0


@dataclass
class StatusFrame:
    """Status feedback to controller."""
    seq: int
    pos_x: int       # Micrometers
    pos_y: int       # Micrometers
    flags: int

    # Flag bits
    HOMED_X = 1 << 0
    HOMED_Y = 1 << 1
    IDLE = 1 << 2
    BUSY = 1 << 3
    ERROR = 1 << 4
    CONNECTED = 1 << 5
    NEEDLE_UP = 1 << 6
    NEEDLE_DOWN = 1 << 7

    @property
    def is_homed(self) -> bool:
        return (self.flags & (self.HOMED_X | self.HOMED_Y)) == (self.HOMED_X | self.HOMED_Y)


@dataclass
class HeartbeatFrame:
    """Dongle heartbeat with statistics."""
    uptime_ms: int
    packets_received: int
    packets_forwarded: int
    crc_errors: int
    last_seq: int
    link_status: int


@dataclass
class ResponseFrame:
    """Response frame from dongle API."""
    response_to: int
    id: int
    status: int
    data: bytes


@dataclass
class DongleInfo:
    """Dongle info response data."""
    protocol_version: int
    firmware_major: int
    firmware_minor: int
    firmware_patch: int
    mac: str
    esp_now_channel: int
    wifi_enabled: int
    controller_count: int
    led_brightness: int


@dataclass
class DongleStatus:
    """Dongle status response data."""
    uptime_ms: int
    packets_rx: int
    packets_tx: int
    crc_errors: int
    link_status: int
    pairing_mode: int
    rssi: int


@dataclass
class PeerInfo:
    """Peer info for registered controllers."""
    slot_id: int
    mac: str
    active: int
    last_seen: int
    packets: int


def _format_mac(mac_bytes: bytes) -> str:
    return ":".join(f"{b:02X}" for b in mac_bytes)


def parse_dongle_info(data: bytes) -> Optional[DongleInfo]:
    """Parse DongleInfo payload data."""
    if len(data) < DONGLE_INFO_SIZE:
        return None

    protocol_version, fw_major, fw_minor, fw_patch, mac_bytes, channel, wifi, count, led = struct.unpack(
        '<BBBB6sBBBB', data[:DONGLE_INFO_SIZE]
    )

    return DongleInfo(
        protocol_version=protocol_version,
        firmware_major=fw_major,
        firmware_minor=fw_minor,
        firmware_patch=fw_patch,
        mac=_format_mac(mac_bytes),
        esp_now_channel=channel,
        wifi_enabled=wifi,
        controller_count=count,
        led_brightness=led
    )


def parse_dongle_status(data: bytes) -> Optional[DongleStatus]:
    """Parse DongleStatus payload data."""
    if len(data) < DONGLE_STATUS_SIZE:
        return None

    uptime_ms, packets_rx, packets_tx, crc_errors, link_status, pairing_mode, rssi = struct.unpack(
        '<IIIHBBb', data[:DONGLE_STATUS_SIZE]
    )

    return DongleStatus(
        uptime_ms=uptime_ms,
        packets_rx=packets_rx,
        packets_tx=packets_tx,
        crc_errors=crc_errors,
        link_status=link_status,
        pairing_mode=pairing_mode,
        rssi=rssi
    )


def parse_peer_list(data: bytes) -> Optional[list[PeerInfo]]:
    """Parse list of PeerInfo entries."""
    if len(data) % PEER_INFO_SIZE != 0:
        return None

    peers = []
    for offset in range(0, len(data), PEER_INFO_SIZE):
        slot_id, mac_bytes, active, last_seen, packets = struct.unpack(
            '<B6sBII', data[offset:offset + PEER_INFO_SIZE]
        )
        peers.append(PeerInfo(
            slot_id=slot_id,
            mac=_format_mac(mac_bytes),
            active=active,
            last_seen=last_seen,
            packets=packets
        ))

    return peers


class FrameParser:
    """
    Parses incoming serial frames from dongle.

    Usage:
        parser = FrameParser()
        for byte in serial_data:
            frame = parser.feed(byte)
            if frame:
                handle_frame(frame)
    """

    def __init__(self):
        self.buffer = bytearray()
        self.in_frame = False
        self.escaped = False

    def reset(self):
        """Reset parser state."""
        self.buffer.clear()
        self.in_frame = False
        self.escaped = False

    def feed(self, byte: int) -> Optional[Union[JoystickFrame, HeartbeatFrame, ResponseFrame]]:
        """
        Feed a single byte to the parser.
        Returns a parsed frame if complete, otherwise None.
        """
        # Handle start byte
        if byte == START_BYTE and not self.escaped:
            self.buffer.clear()
            self.in_frame = True
            self.escaped = False
            return None

        # Handle end byte
        if byte == END_BYTE and not self.escaped:
            if self.in_frame and len(self.buffer) >= 4:
                frame = self._parse_buffer()
                self.reset()
                return frame
            self.reset()
            return None

        # Handle escape byte
        if byte == ESCAPE_BYTE and not self.escaped:
            self.escaped = True
            return None

        # De-escape if needed
        if self.escaped:
            byte ^= ESCAPE_XOR
            self.escaped = False

        # Accumulate data
        if self.in_frame:
            self.buffer.append(byte)
            # Prevent buffer overflow
            if len(self.buffer) > 256:
                self.reset()

        return None

    def _parse_buffer(self) -> Optional[Union[JoystickFrame, HeartbeatFrame, ResponseFrame]]:
        """Parse accumulated buffer into a frame."""
        if len(self.buffer) < 4:
            return None

        msg_type = self.buffer[0]
        msg_len = self.buffer[1]

        # Check we have enough data: type(1) + len(1) + payload(msg_len) + crc(2)
        expected_len = 2 + msg_len + 2
        if len(self.buffer) < expected_len:
            logger.debug(f"Short frame: {len(self.buffer)} < {expected_len}")
            return None

        payload = bytes(self.buffer[2:2 + msg_len])
        crc_received = self.buffer[2 + msg_len] | (self.buffer[3 + msg_len] << 8)

        # Verify CRC over type + len + payload
        crc_data = bytes(self.buffer[:2 + msg_len])
        crc_calculated = crc16_ccitt(crc_data)

        if crc_received != crc_calculated:
            logger.warning(f"CRC mismatch: received=0x{crc_received:04X}, calculated=0x{crc_calculated:04X}")
            return None

        # Parse based on message type
        if msg_type == MSG_TYPE_JOYSTICK_EXT and msg_len == JOYSTICK_EXT_SIZE:
            return self._parse_joystick_ext(payload)
        elif msg_type == MSG_TYPE_JOYSTICK and msg_len == JOYSTICK_FRAME_SIZE:
            return self._parse_joystick(payload, controller_id=0)
        elif msg_type == MSG_TYPE_HEARTBEAT and msg_len == HEARTBEAT_FRAME_SIZE:
            return self._parse_heartbeat(payload)
        elif msg_type == MSG_TYPE_RESPONSE:
            return self._parse_response(payload)
        else:
            logger.debug(f"Unknown message type: 0x{msg_type:02X}, len={msg_len}")
            return None

    def _parse_joystick_ext(self, payload: bytes) -> Optional[JoystickFrame]:
        """Parse extended joystick frame (with controller ID)."""
        if len(payload) < JOYSTICK_EXT_SIZE:
            return None

        controller_id = payload[0]
        return self._parse_joystick(payload[1:], controller_id)

    def _parse_joystick(self, payload: bytes, controller_id: int) -> Optional[JoystickFrame]:
        """Parse joystick frame."""
        if len(payload) < JOYSTICK_FRAME_SIZE:
            return None

        # Unpack: seq(H) + vx(h) + vy(h) + deadman(B) + buttons(B) + ui_action(B) + ui_value(B) + crc(H)
        try:
            seq, vx, vy, deadman, buttons, ui_action, ui_value, crc = struct.unpack(
                '<HhhBBBBH', payload[:JOYSTICK_FRAME_SIZE]
            )
        except struct.error as e:
            logger.warning(f"Failed to unpack joystick frame: {e}")
            return None

        # Verify internal CRC (over first 10 bytes, before CRC field)
        internal_crc = crc16_ccitt(payload[:10])
        if crc != internal_crc:
            logger.warning(f"Joystick CRC mismatch: received=0x{crc:04X}, calculated=0x{internal_crc:04X}")
            return None

        return JoystickFrame(
            controller_id=controller_id,
            seq=seq,
            vx=vx,
            vy=vy,
            deadman=bool(deadman),
            buttons=buttons,
            ui_action=ui_action,
            ui_value=ui_value
        )

    def _parse_heartbeat(self, payload: bytes) -> Optional[HeartbeatFrame]:
        """Parse heartbeat frame."""
        if len(payload) < HEARTBEAT_FRAME_SIZE:
            return None

        try:
            uptime, rx, fwd, crc_err, last_seq, link, crc = struct.unpack(
                '<IIIHHBH', payload[:HEARTBEAT_FRAME_SIZE]
            )
        except struct.error as e:
            logger.warning(f"Failed to unpack heartbeat frame: {e}")
            return None

        # Verify internal CRC
        internal_crc = crc16_ccitt(payload[:17])
        if crc != internal_crc:
            logger.warning(f"Heartbeat CRC mismatch")
            return None

        return HeartbeatFrame(
            uptime_ms=uptime,
            packets_received=rx,
            packets_forwarded=fwd,
            crc_errors=crc_err,
            last_seq=last_seq,
            link_status=link
        )

    def _parse_response(self, payload: bytes) -> Optional[ResponseFrame]:
        """Parse a dongle API response frame."""
        if len(payload) < 6:
            return None

        response_to, resp_id, status, data_len = struct.unpack('<BBBB', payload[:4])
        expected_len = 4 + data_len + 2
        if len(payload) < expected_len:
            return None

        data = payload[4:4 + data_len]
        crc_received = struct.unpack('<H', payload[4 + data_len:expected_len])[0]
        crc_calculated = crc16_ccitt(payload[:4 + data_len])

        if crc_received != crc_calculated:
            logger.warning("Response CRC mismatch")
            return None

        return ResponseFrame(
            response_to=response_to,
            id=resp_id,
            status=status,
            data=data
        )


class FrameBuilder:
    """Builds frames to send to dongle."""

    @staticmethod
    def build_status(frame: StatusFrame) -> bytes:
        """Build a status frame to send to dongle."""
        # Pack payload: seq(H) + pos_x(i) + pos_y(i) + flags(B)
        payload = struct.pack('<HiiB', frame.seq, frame.pos_x, frame.pos_y, frame.flags)

        # Calculate and append CRC
        crc = crc16_ccitt(payload)
        payload += struct.pack('<H', crc)

        # Build framed message
        return FrameBuilder._build_frame(MSG_TYPE_STATUS, payload)

    @staticmethod
    def build_query(query_id: int) -> bytes:
        """Build a query frame to send to dongle."""
        payload = struct.pack('<BB', query_id, 0)
        crc = crc16_ccitt(payload)
        payload += struct.pack('<H', crc)

        return FrameBuilder._build_frame(MSG_TYPE_QUERY, payload)

    @staticmethod
    def build_command(cmd_id: int, param: int) -> bytes:
        """Build a command frame to send to dongle."""
        payload = struct.pack('<BB', cmd_id, param)
        crc = crc16_ccitt(payload)
        payload += struct.pack('<H', crc)

        return FrameBuilder._build_frame(MSG_TYPE_COMMAND, payload)

    @staticmethod
    def _build_frame(msg_type: int, payload: bytes) -> bytes:
        """Build a complete framed message with escaping."""
        # Header: type + length
        header = bytes([msg_type, len(payload)])

        # CRC over header + payload
        crc = crc16_ccitt(header + payload)
        crc_bytes = struct.pack('<H', crc)

        # Combine all parts
        raw = header + payload + crc_bytes

        # Escape and frame
        result = bytearray([START_BYTE])
        for b in raw:
            if b in (START_BYTE, END_BYTE, ESCAPE_BYTE):
                result.append(ESCAPE_BYTE)
                result.append(b ^ ESCAPE_XOR)
            else:
                result.append(b)
        result.append(END_BYTE)

        return bytes(result)

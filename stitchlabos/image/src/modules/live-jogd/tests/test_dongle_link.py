"""Dongle queries and commands share the daemon's serial connection.

The read loop runs against a fake port: every byte the daemon sees arrives
through _serial_read_loop and FrameParser, as on the Pi.
"""

import asyncio
import struct

import pytest

import config
import live_jogd
from serial_protocol import (
    FrameBuilder,
    FrameParser,
    crc16_ccitt,
    MSG_TYPE_COMMAND,
    MSG_TYPE_JOYSTICK_EXT,
    MSG_TYPE_QUERY,
    MSG_TYPE_RESPONSE,
    CMD_WIFI_ENABLE,
    QUERY_INFO,
    QUERY_PEERS,
    RESP_OK,
)


def response_frame(response_to: int, request_id: int, data: bytes = b"",
                   status: int = RESP_OK) -> bytes:
    payload = struct.pack("<BBBB", response_to, request_id, status, len(data)) + data
    payload += struct.pack("<H", crc16_ccitt(payload))
    return FrameBuilder._build_frame(MSG_TYPE_RESPONSE, payload)


def joystick_frame(controller_id: int, seq: int) -> bytes:
    body = struct.pack("<HhhBBBB", seq, 0, 0, 0, 0, 0, 0)
    body += struct.pack("<H", crc16_ccitt(body))
    return FrameBuilder._build_frame(MSG_TYPE_JOYSTICK_EXT, bytes([controller_id]) + body)


def info_payload() -> bytes:
    return struct.pack("<BBBB6sBBBB", 1, 1, 2, 3, bytes(range(6)), 6, 1, 2, 128)


def peer_payload(*peers) -> bytes:
    return b"".join(
        struct.pack("<B6sBII", slot, bytes([slot] * 6), active, 0, 0)
        for slot, active in peers
    )


class FakeSerial:
    """Serial port stand-in; `responder` answers what the daemon writes."""

    def __init__(self, responder=None):
        self.is_open = True
        self.rx = bytearray()
        self.written = []
        self.responder = responder

    @property
    def in_waiting(self) -> int:
        return len(self.rx)

    def read(self, n: int) -> bytes:
        data = bytes(self.rx[:n])
        del self.rx[:n]
        return data

    def write(self, data: bytes) -> int:
        self.written.append(data)
        if self.responder:
            self.rx += self.responder(data)
        return len(data)


def decode(data: bytes):
    """Return (msg_type, id) of a frame the daemon wrote."""
    parser = FrameParser()
    for byte in data[:-1]:
        parser.feed(byte)
    raw = parser.buffer
    return raw[0], raw[2]


@pytest.fixture
def daemon(monkeypatch):
    async def no_subprocess(*args, **kwargs):
        raise AssertionError(f"dongle access through a subprocess: {args}")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", no_subprocess)
    d = live_jogd.LiveJogDaemon()
    d.running = True
    d.dongle_connected = True
    d.joystick_frames = []

    async def record_joystick(frame):
        d.joystick_frames.append(frame.seq)

    d._handle_joystick = record_joystick
    return d


async def run_with_read_loop(daemon, coro):
    reader = asyncio.create_task(daemon._serial_read_loop())
    try:
        return await coro
    finally:
        daemon.running = False
        await reader


@pytest.mark.asyncio
async def test_query_answered_over_daemon_port(daemon):
    def responder(data):
        assert decode(data) == (MSG_TYPE_QUERY, QUERY_INFO)
        return response_frame(MSG_TYPE_QUERY, QUERY_INFO, info_payload())

    daemon.serial_port = FakeSerial(responder)
    data = await run_with_read_loop(daemon, daemon._dongle_query(QUERY_INFO))
    assert data == info_payload()
    assert daemon._dongle_pending is None


@pytest.mark.asyncio
async def test_joystick_frames_around_a_response_are_kept(daemon):
    # The failure mode of the old subprocess path: frames arriving while a
    # query is in flight were flushed or read by the other process.
    daemon.peers = [{"slot_id": 3, "mac": "", "active": True}]

    def responder(data):
        return (joystick_frame(3, 1)
                + response_frame(MSG_TYPE_QUERY, QUERY_INFO, info_payload())
                + joystick_frame(3, 2))

    daemon.serial_port = FakeSerial(responder)

    async def query_then_drain():
        data = await daemon._dongle_query(QUERY_INFO)
        while daemon.serial_port.in_waiting:
            await asyncio.sleep(0.005)
        await asyncio.sleep(0.01)
        return data

    assert await run_with_read_loop(daemon, query_then_drain()) == info_payload()
    assert daemon.joystick_frames == [1, 2]


@pytest.mark.asyncio
async def test_unanswered_request_times_out(daemon, monkeypatch):
    monkeypatch.setattr(config, "DONGLE_REQUEST_TIMEOUT_S", 0.05)
    daemon.serial_port = FakeSerial()
    assert await run_with_read_loop(daemon, daemon._dongle_query(QUERY_INFO)) is None
    assert daemon._dongle_pending is None


@pytest.mark.asyncio
async def test_error_status_fails_command(daemon):
    def responder(data):
        assert decode(data) == (MSG_TYPE_COMMAND, CMD_WIFI_ENABLE)
        return response_frame(MSG_TYPE_COMMAND, CMD_WIFI_ENABLE, status=0x01)

    daemon.serial_port = FakeSerial(responder)
    daemon.dongle_info["wifi_enabled"] = True
    ok = await run_with_read_loop(daemon, daemon._dongle_set_wifi(False))
    assert ok is False
    assert daemon.dongle_info["wifi_enabled"] is True


@pytest.mark.asyncio
async def test_response_for_other_request_is_ignored(daemon, monkeypatch):
    monkeypatch.setattr(config, "DONGLE_REQUEST_TIMEOUT_S", 0.05)
    daemon.serial_port = FakeSerial(
        lambda data: response_frame(MSG_TYPE_QUERY, QUERY_PEERS, peer_payload()))
    assert await run_with_read_loop(daemon, daemon._dongle_query(QUERY_INFO)) is None


@pytest.mark.asyncio
async def test_query_loop_keeps_selected_controller(daemon, monkeypatch):
    # User selected slot 2; the dongle flags slot 1 as active.
    daemon.peers = [
        {"slot_id": 1, "mac": "", "active": False},
        {"slot_id": 2, "mac": "", "active": True},
    ]

    def responder(data):
        msg_type, request_id = decode(data)
        payload = peer_payload((1, 1), (2, 0)) if request_id == QUERY_PEERS else b""
        return response_frame(msg_type, request_id, payload)

    daemon.serial_port = FakeSerial(responder)

    class OneRoundDone(Exception):
        pass

    async def one_query_round():
        real_sleep = asyncio.sleep

        async def fast_sleep(delay):
            if delay == 5:
                # Skip the poll interval; end the loop after one round.
                if daemon.serial_port.written:
                    raise OneRoundDone
                return await real_sleep(0)
            return await real_sleep(delay)

        monkeypatch.setattr(asyncio, "sleep", fast_sleep)
        with pytest.raises(OneRoundDone):
            await daemon._dongle_query_loop()

    await run_with_read_loop(daemon, one_query_round())
    assert [(p["slot_id"], p["active"]) for p in daemon.peers] == [(1, False), (2, True)]
    assert daemon.peers[0]["mac"] == "01:01:01:01:01:01"


def test_merge_without_selection_adopts_one_dongle_active_peer(daemon):
    daemon._merge_dongle_peers([
        {"slot_id": 1, "mac": "", "active": False},
        {"slot_id": 2, "mac": "", "active": True},
        {"slot_id": 3, "mac": "", "active": True},
    ])
    assert [p["slot_id"] for p in daemon.peers if p["active"]] == [2]

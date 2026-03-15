#!/usr/bin/env python3
"""
Minimal dongle API client for querying the ESP32-C3 dongle over serial.
"""

import argparse
import time
import serial

from serial_protocol import (
    FrameParser,
    FrameBuilder,
    ResponseFrame,
    parse_dongle_info,
    parse_dongle_status,
    parse_peer_list,
    QUERY_INFO,
    QUERY_STATUS,
    QUERY_PEERS,
    CMD_WIFI_ENABLE,
    CMD_ENTER_PAIRING,
    CMD_EXIT_PAIRING,
    CMD_CLEAR_PEERS,
    CMD_SAVE_CONFIG,
    RESP_OK,
    MSG_TYPE_QUERY,
    MSG_TYPE_COMMAND,
)
import config


def wait_for_response(port: str, baud: int, timeout: float, payload: bytes,
                      response_to: int, expected_id: int):
    parser = FrameParser()
    deadline = time.monotonic() + timeout

    ser = serial.Serial(port=port, baudrate=baud, timeout=0)
    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write(payload)

        while time.monotonic() < deadline:
            data = ser.read(ser.in_waiting or 1)
            if not data:
                time.sleep(0.01)
                continue

            for byte in data:
                frame = parser.feed(byte)
                if isinstance(frame, ResponseFrame):
                    if (frame.response_to == response_to and
                            frame.id == expected_id and
                            frame.status == RESP_OK):
                        return frame.data
        return None
    finally:
        ser.close()


def query_frame(port: str, baud: int, timeout: float, query_id: int):
    payload = FrameBuilder.build_query(query_id)
    return wait_for_response(port, baud, timeout, payload, MSG_TYPE_QUERY, query_id)


def send_command(port: str, baud: int, timeout: float, cmd_id: int, param: int):
    payload = FrameBuilder.build_command(cmd_id, param)
    return wait_for_response(port, baud, timeout, payload, MSG_TYPE_COMMAND, cmd_id)


def main():
    parser = argparse.ArgumentParser(description="Query dongle info via serial API.")
    parser.add_argument("--port", default=config.SERIAL_PORT, help="Serial device path")
    parser.add_argument("--baud", type=int, default=config.SERIAL_BAUD, help="Serial baud rate")
    parser.add_argument("--timeout", type=float, default=2.0, help="Seconds to wait for reply")
    parser.add_argument("--query", choices=["info", "status", "peers"], default="info",
                        help="Query type")
    parser.add_argument("--wifi", choices=["on", "off"], default=None,
                        help="Enable/disable ESP-NOW/WiFi on the dongle")
    parser.add_argument("--pairing", choices=["on", "off"], default=None,
                        help="Enable/disable pairing mode")
    parser.add_argument("--clear-peers", action="store_true",
                        help="Clear stored controller pairing")
    parser.add_argument("--save", action="store_true",
                        help="Persist current dongle settings to NVS")
    parser.add_argument("--watch", type=float, default=0.0,
                        help="Poll interval in seconds (0 = once)")
    args = parser.parse_args()

    if args.clear_peers:
        result = send_command(args.port, args.baud, args.timeout, CMD_CLEAR_PEERS, 0)
        if result is None:
            raise SystemExit("No response from dongle.")
        print("Peers cleared")
        return

    if args.pairing is not None:
        cmd = CMD_ENTER_PAIRING if args.pairing == "on" else CMD_EXIT_PAIRING
        result = send_command(args.port, args.baud, args.timeout, cmd, 0)
        if result is None:
            raise SystemExit("No response from dongle.")
        print(f"Pairing: {args.pairing}")
        return

    if args.wifi is not None:
        param = 1 if args.wifi == "on" else 0
        result = send_command(args.port, args.baud, args.timeout, CMD_WIFI_ENABLE, param)
        if result is None:
            raise SystemExit("No response from dongle.")

        if args.save:
            result = send_command(args.port, args.baud, args.timeout, CMD_SAVE_CONFIG, 0)
            if result is None:
                raise SystemExit("Failed to save config.")

        print(f"WiFi: {args.wifi}")
        return

    query_id = {
        "info": QUERY_INFO,
        "status": QUERY_STATUS,
        "peers": QUERY_PEERS,
    }[args.query]

    while True:
        data = query_frame(args.port, args.baud, args.timeout, query_id)
        if not data:
            raise SystemExit("No response from dongle.")

        if args.query == "info":
            info = parse_dongle_info(data)
            if not info:
                raise SystemExit("Failed to parse dongle info.")
            print(f"MAC: {info.mac}")
            print(f"FW: {info.firmware_major}.{info.firmware_minor}.{info.firmware_patch}")
            print(f"Channel: {info.esp_now_channel}")
            print(f"WiFi: {'on' if info.wifi_enabled else 'off'}")
            print(f"Controllers: {info.controller_count}")
            print(f"LED brightness: {info.led_brightness}")
        elif args.query == "status":
            status = parse_dongle_status(data)
            if not status:
                raise SystemExit("Failed to parse dongle status.")
            print(f"Uptime: {status.uptime_ms} ms")
            print(f"Packets RX: {status.packets_rx}")
            print(f"Packets TX: {status.packets_tx}")
            print(f"CRC errors: {status.crc_errors}")
            print(f"Link: {status.link_status}")
            print(f"Pairing: {status.pairing_mode}")
            print(f"RSSI: {status.rssi}")
        else:
            peers = parse_peer_list(data)
            if peers is None:
                raise SystemExit("Failed to parse peers.")
            if not peers:
                print("No peers.")
            for peer in peers:
                print(
                    f"slot={peer.slot_id} mac={peer.mac} active={peer.active} "
                    f"last_seen={peer.last_seen} packets={peer.packets}"
                )

        if args.watch <= 0:
            break

        time.sleep(args.watch)


if __name__ == "__main__":
    main()

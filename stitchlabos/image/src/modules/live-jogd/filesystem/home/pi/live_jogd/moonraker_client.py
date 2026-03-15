"""
Moonraker API Client

Async HTTP client for Moonraker/Klipper communication.
"""

import aiohttp
import asyncio
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class MoonrakerClient:
    """Async client for Moonraker API."""

    def __init__(self, host: str = "localhost", port: int = 7125):
        self.base_url = f"http://{host}:{port}"
        self._session: Optional[aiohttp.ClientSession] = None
        self._connected = False

    async def connect(self):
        """Initialize HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            )
        self._connected = True

    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def _get(self, endpoint: str) -> Optional[dict]:
        """HTTP GET request."""
        if not self._session:
            await self.connect()

        try:
            async with self._session.get(f"{self.base_url}{endpoint}") as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.warning(f"GET {endpoint} returned {resp.status}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"GET {endpoint} failed: {e}")
            self._connected = False
            return None

    async def _post(self, endpoint: str, data: Optional[dict] = None) -> Optional[dict]:
        """HTTP POST request."""
        if not self._session:
            await self.connect()

        try:
            async with self._session.post(f"{self.base_url}{endpoint}", json=data) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.warning(f"POST {endpoint} returned {resp.status}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"POST {endpoint} failed: {e}")
            self._connected = False
            return None

    async def get_printer_info(self) -> Optional[dict]:
        """Get printer info."""
        return await self._get("/printer/info")

    async def get_position(self) -> Tuple[float, float, float]:
        """
        Get current toolhead position.
        Returns (x, y, z) in mm, or (0, 0, 0) on error.
        """
        result = await self._get("/printer/objects/query?toolhead")
        if result and "result" in result:
            status = result["result"].get("status", {})
            toolhead = status.get("toolhead", {})
            pos = toolhead.get("position", [0, 0, 0, 0])
            return (pos[0], pos[1], pos[2])
        return (0.0, 0.0, 0.0)

    async def get_homed_axes(self) -> str:
        """
        Get which axes are homed.
        Returns string like 'xy', 'xyz', '' etc.
        """
        result = await self._get("/printer/objects/query?toolhead")
        if result and "result" in result:
            status = result["result"].get("status", {})
            toolhead = status.get("toolhead", {})
            return toolhead.get("homed_axes", "")
        return ""

    async def is_homed(self, axes: str = "xy") -> bool:
        """Check if specified axes are homed."""
        homed = await self.get_homed_axes()
        return all(axis in homed for axis in axes.lower())

    async def get_printer_state(self) -> str:
        """
        Get printer state.
        Returns: 'ready', 'printing', 'error', 'paused', 'shutdown', etc.
        """
        result = await self._get("/printer/objects/query?print_stats")
        if result and "result" in result:
            status = result["result"].get("status", {})
            print_stats = status.get("print_stats", {})
            return print_stats.get("state", "unknown")
        return "unknown"

    async def is_idle(self) -> bool:
        """Check if printer is idle and ready for jogging."""
        state = await self.get_printer_state()
        return state in ("ready", "standby", "complete")

    async def gcode(self, script: str) -> bool:
        """
        Send G-code script to Klipper.
        Returns True on success.
        """
        result = await self._post("/printer/gcode/script", {"script": script})
        return result is not None

    async def emergency_stop(self) -> bool:
        """Trigger emergency stop."""
        logger.warning("EMERGENCY STOP triggered!")
        result = await self._post("/printer/emergency_stop")
        return result is not None

    async def home(self, axes: str = "xyz") -> bool:
        """
        Home specified axes.
        axes: 'x', 'y', 'z', 'xy', 'xyz', etc.
        """
        axis_str = " ".join(axes.upper())
        return await self.gcode(f"G28 {axis_str}")

    async def jog_relative(self, x: float = 0, y: float = 0, z: float = 0, feedrate: float = 6000) -> bool:
        """
        Move relative by specified amounts.
        x, y, z in mm
        feedrate in mm/min
        """
        parts = ["G91"]  # Relative mode

        move_parts = []
        if x != 0:
            move_parts.append(f"X{x:.3f}")
        if y != 0:
            move_parts.append(f"Y{y:.3f}")
        if z != 0:
            move_parts.append(f"Z{z:.3f}")

        if move_parts:
            parts.append(f"G1 {' '.join(move_parts)} F{feedrate:.0f}")
            return await self.gcode("\n".join(parts))

        return True

    async def run_macro(self, macro_name: str) -> bool:
        """Run a Klipper macro."""
        return await self.gcode(macro_name)


async def test_connection():
    """Test Moonraker connection."""
    client = MoonrakerClient()
    await client.connect()

    try:
        info = await client.get_printer_info()
        if info:
            print(f"Connected to Moonraker")
            print(f"State: {info.get('result', {}).get('state', 'unknown')}")

        pos = await client.get_position()
        print(f"Position: X={pos[0]:.2f} Y={pos[1]:.2f} Z={pos[2]:.2f}")

        homed = await client.get_homed_axes()
        print(f"Homed axes: {homed or 'none'}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_connection())

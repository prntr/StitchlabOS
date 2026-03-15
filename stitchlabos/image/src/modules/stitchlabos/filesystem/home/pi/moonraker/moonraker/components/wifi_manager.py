# WiFi Manager Component for Moonraker
# Provides API endpoints for WiFi management via AccessPopup/NetworkManager
#
# Copyright (C) 2024 StitchLabOS
# This file may be distributed under the terms of the GNU GPLv3 license.

from __future__ import annotations
import logging
import json
import re

from ..common import RequestType

from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
)

if TYPE_CHECKING:
    from ..confighelper import ConfigHelper
    from ..common import WebRequest
    from .shell_command import ShellCommandFactory as SCMDComp


SCRIPTS_PATH = "/home/pi/printer_data/scripts"


class WiFiManager:
    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.shell_cmd: SCMDComp = self.server.load_component(
            config, 'shell_command'
        )

        # Register API endpoints
        self.server.register_endpoint(
            "/server/wifi/status",
            RequestType.GET,
            self._handle_status
        )
        self.server.register_endpoint(
            "/server/wifi/scan",
            RequestType.GET,
            self._handle_scan
        )
        self.server.register_endpoint(
            "/server/wifi/profiles",
            RequestType.GET,
            self._handle_profiles
        )
        self.server.register_endpoint(
            "/server/wifi/connect",
            RequestType.POST,
            self._handle_connect
        )
        self.server.register_endpoint(
            "/server/wifi/disconnect",
            RequestType.POST,
            self._handle_disconnect
        )
        self.server.register_endpoint(
            "/server/wifi/ap/enable",
            RequestType.POST,
            self._handle_ap_enable
        )
        self.server.register_endpoint(
            "/server/wifi/ap/disable",
            RequestType.POST,
            self._handle_ap_disable
        )
        self.server.register_endpoint(
            "/server/wifi/forget",
            RequestType.POST,
            self._handle_forget
        )
        # NEW: Add network endpoint
        self.server.register_endpoint(
            "/server/wifi/add",
            RequestType.POST,
            self._handle_add_network
        )
        # NEW: Update profile priority
        self.server.register_endpoint(
            "/server/wifi/priority",
            RequestType.POST,
            self._handle_set_priority
        )
        # NEW: Configure AP settings
        self.server.register_endpoint(
            "/server/wifi/ap/configure",
            RequestType.POST,
            self._handle_ap_configure
        )
        # NEW: Get AP configuration
        self.server.register_endpoint(
            "/server/wifi/ap/config",
            RequestType.GET,
            self._handle_ap_get_config
        )

        logging.info("WiFiManager: Component loaded (extended)")

    async def _run_script(self, script_name: str, timeout: float = 10.0) -> str:
        """Run a script from the scripts directory and return output."""
        script_path = f"{SCRIPTS_PATH}/{script_name}"
        try:
            result = await self.shell_cmd.exec_cmd(
                script_path,
                timeout=timeout,
                log_complete=False
            )
            return result
        except self.shell_cmd.error as e:
            logging.error(f"WiFiManager: Script {script_name} failed: {e}")
            raise self.server.error(f"Script execution failed: {e}", 500)

    async def _run_nmcli(self, cmd: str, timeout: float = 30.0) -> str:
        """Run an nmcli command and return output."""
        try:
            result = await self.shell_cmd.exec_cmd(
                cmd,
                timeout=timeout,
                log_complete=False
            )
            return result
        except self.shell_cmd.error as e:
            logging.error(f"WiFiManager: nmcli command failed: {e}")
            raise self.server.error(f"Command execution failed: {e}", 500)

    async def _run_nmcli_privileged(self, cmd: str, timeout: float = 30.0) -> str:
        """Run an nmcli command with sudo and return output."""
        return await self._run_nmcli(f"sudo -n {cmd}", timeout=timeout)

    async def _try_nmcli(self, cmd: str, timeout: float = 30.0) -> tuple[bool, str]:
        """Run an nmcli command and return success plus output/error."""
        try:
            result = await self.shell_cmd.exec_cmd(
                cmd,
                timeout=timeout,
                log_complete=False
            )
            return True, result
        except self.shell_cmd.error as e:
            return False, str(e)

    async def _try_nmcli_privileged(self, cmd: str, timeout: float = 30.0) -> tuple[bool, str]:
        """Run an nmcli command with sudo and return success plus output/error."""
        return await self._try_nmcli(f"sudo -n {cmd}", timeout=timeout)

    async def _handle_status(self, web_request: WebRequest) -> Dict[str, Any]:
        """Get current WiFi connection status."""
        output = await self._run_script("wifi_status.sh")
        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            logging.error(f"WiFiManager: Failed to parse status JSON: {e}")
            raise self.server.error(f"Failed to parse status: {e}", 500)

    async def _handle_scan(self, web_request: WebRequest) -> Dict[str, Any]:
        """Scan for available WiFi networks."""
        # Force a rescan first
        try:
            await self.shell_cmd.exec_cmd(
                "nmcli device wifi rescan",
                timeout=10.0,
                log_complete=False,
                success_codes=[0, 1]  # May return 1 if scan already in progress
            )
        except self.shell_cmd.error:
            pass  # Ignore rescan errors

        output = await self._run_script("wifi_scan.sh")
        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            logging.error(f"WiFiManager: Failed to parse scan JSON: {e}")
            raise self.server.error(f"Failed to parse scan results: {e}", 500)

    async def _handle_profiles(self, web_request: WebRequest) -> Dict[str, Any]:
        """Get saved WiFi profiles."""
        output = await self._run_script("wifi_profiles.sh")
        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            logging.error(f"WiFiManager: Failed to parse profiles JSON: {e}")
            raise self.server.error(f"Failed to parse profiles: {e}", 500)

    async def _handle_connect(self, web_request: WebRequest) -> Dict[str, Any]:
        """Connect to a WiFi network."""
        ssid = web_request.get_str("ssid")
        password = web_request.get_str("password", None)

        if not ssid:
            raise self.server.error("SSID is required", 400)

        # Check if this is a saved profile
        profiles_output = await self._run_script("wifi_profiles.sh")
        try:
            profiles_data = json.loads(profiles_output)
            saved_profiles = [p["name"] for p in profiles_data.get("profiles", [])]
        except (json.JSONDecodeError, KeyError):
            saved_profiles = []

        if ssid in saved_profiles:
            # Connect to saved profile
            cmd = f'nmcli connection up "{ssid}"'
        elif password:
            # Connect to new network with password
            cmd = f'nmcli device wifi connect "{ssid}" password "{password}"'
        else:
            # Try connecting to open network or saved profile by SSID
            cmd = f'nmcli device wifi connect "{ssid}"'

        try:
            result = await self._run_nmcli_privileged(cmd, timeout=60.0)
            logging.info(f"WiFiManager: Connected to {ssid}")
            return {"status": "connected", "ssid": ssid, "message": result}
        except Exception as e:
            raise self.server.error(f"Failed to connect to {ssid}: {e}", 500)

    async def _handle_disconnect(self, web_request: WebRequest) -> Dict[str, Any]:
        """Disconnect from current WiFi network."""
        try:
            await self._run_nmcli_privileged("nmcli device disconnect wlan0")
            logging.info("WiFiManager: Disconnected from WiFi")
            return {"status": "disconnected"}
        except Exception as e:
            raise self.server.error(f"Failed to disconnect: {e}", 500)

    async def _handle_ap_enable(self, web_request: WebRequest) -> Dict[str, Any]:
        """Enable Access Point mode."""
        ap_profile = web_request.get_str("profile", "AccessPopup")

        try:
            # Disconnect any existing connection
            try:
                await self._run_nmcli_privileged("nmcli device disconnect wlan0", timeout=10.0)
            except Exception:
                pass  # Ignore if already disconnected

            # Activate AP profile
            cmd = f'nmcli connection up "{ap_profile}"'
            result = await self._run_nmcli_privileged(cmd, timeout=30.0)
            logging.info(f"WiFiManager: AP mode enabled with profile {ap_profile}")
            return {"status": "ap_enabled", "profile": ap_profile, "message": result}
        except Exception as e:
            raise self.server.error(f"Failed to enable AP mode: {e}", 500)

    async def _handle_ap_disable(self, web_request: WebRequest) -> Dict[str, Any]:
        """Disable Access Point mode and attempt to reconnect to WiFi."""
        try:
            # Disconnect AP
            await self._run_nmcli_privileged("nmcli device disconnect wlan0", timeout=10.0)

            # Try to connect to the first available saved network
            profiles_output = await self._run_script("wifi_profiles.sh")
            try:
                profiles_data = json.loads(profiles_output)
                wifi_profiles = [
                    p["name"] for p in profiles_data.get("profiles", [])
                    if p.get("type") == "wifi"
                ]
            except (json.JSONDecodeError, KeyError):
                wifi_profiles = []

            if wifi_profiles:
                # Try to connect to the first WiFi profile
                try:
                    cmd = f'nmcli connection up "{wifi_profiles[0]}"'
                    await self._run_nmcli_privileged(cmd, timeout=60.0)
                    logging.info(f"WiFiManager: Reconnected to {wifi_profiles[0]}")
                    return {
                        "status": "reconnected",
                        "ssid": wifi_profiles[0]
                    }
                except Exception:
                    pass

            logging.info("WiFiManager: AP disabled, no WiFi reconnection")
            return {"status": "ap_disabled"}
        except Exception as e:
            raise self.server.error(f"Failed to disable AP mode: {e}", 500)

    async def _handle_forget(self, web_request: WebRequest) -> Dict[str, Any]:
        """Forget (delete) a saved WiFi profile."""
        profile = web_request.get_str("profile")

        if not profile:
            raise self.server.error("Profile name is required", 400)

        # Don't allow deleting the AP profile
        if profile.lower() == "accesspopup":
            raise self.server.error("Cannot delete the AccessPopup profile", 400)

        try:
            cmd = f'nmcli connection delete "{profile}"'
            await self._run_nmcli_privileged(cmd)
            logging.info(f"WiFiManager: Deleted profile {profile}")
            return {"status": "deleted", "profile": profile}
        except Exception as e:
            raise self.server.error(f"Failed to delete profile {profile}: {e}", 500)

    async def _handle_add_network(self, web_request: WebRequest) -> Dict[str, Any]:
        """Add a new WiFi network profile (without connecting)."""
        ssid = web_request.get_str("ssid")
        password = web_request.get_str("password", None)
        autoconnect = web_request.get_boolean("autoconnect", True)
        priority = web_request.get_int("priority", 0)

        if not ssid:
            raise self.server.error("SSID is required", 400)

        # Sanitize SSID for use as connection name
        conn_name = re.sub(r'[^a-zA-Z0-9_-]', '_', ssid)

        try:
            # Check for existing profile
            exists, _ = await self._try_nmcli(
                f'nmcli -t -f NAME connection show "{conn_name}"',
                timeout=5.0
            )

            if password:
                key_mgmt_candidates = ["wpa-psk", "sae"]
                last_error = ""
                if exists:
                    ok, err = await self._try_nmcli_privileged(
                        f'nmcli connection modify "{conn_name}" wireless.ssid "{ssid}"'
                    )
                    if not ok:
                        raise self.server.error(f"Failed to update profile {conn_name}: {err}", 500)
                    for key_mgmt in key_mgmt_candidates:
                        ok, err = await self._try_nmcli_privileged(
                            f'nmcli connection modify "{conn_name}" '
                            f'wifi-sec.key-mgmt {key_mgmt} wifi-sec.psk "{password}"'
                        )
                        if ok:
                            last_error = ""
                            break
                        last_error = err
                else:
                    for key_mgmt in key_mgmt_candidates:
                        ok, err = await self._try_nmcli_privileged(
                            f'nmcli connection add type wifi con-name "{conn_name}" '
                            f'ssid "{ssid}" wifi-sec.key-mgmt {key_mgmt} '
                            f'wifi-sec.psk "{password}"'
                        )
                        if ok:
                            last_error = ""
                            break
                        last_error = err
                        # Clean up any partial profile before retrying
                        await self._try_nmcli_privileged(f'nmcli connection delete "{conn_name}"', timeout=10.0)
                if last_error:
                    raise self.server.error(f"Failed to add network {ssid}: {last_error}", 500)
            else:
                if exists:
                    ok, err = await self._try_nmcli_privileged(
                        f'nmcli connection modify "{conn_name}" wireless.ssid "{ssid}"'
                    )
                    if not ok:
                        raise self.server.error(f"Failed to update profile {conn_name}: {err}", 500)
                else:
                    ok, err = await self._try_nmcli_privileged(
                        f'nmcli connection add type wifi con-name "{conn_name}" '
                        f'ssid "{ssid}"'
                    )
                    if not ok:
                        raise self.server.error(f"Failed to add network {ssid}: {err}", 500)

            # Set autoconnect and priority
            await self._run_nmcli_privileged(
                f'nmcli connection modify "{conn_name}" '
                f'connection.autoconnect {"yes" if autoconnect else "no"} '
                f'connection.autoconnect-priority {priority}'
            )

            logging.info(f"WiFiManager: Added network profile {conn_name}")
            return {
                "status": "added",
                "ssid": ssid,
                "profile": conn_name,
                "autoconnect": autoconnect,
                "priority": priority
            }
        except Exception as e:
            raise self.server.error(f"Failed to add network {ssid}: {e}", 500)

    async def _handle_set_priority(self, web_request: WebRequest) -> Dict[str, Any]:
        """Set the autoconnect priority for a profile."""
        profile = web_request.get_str("profile")
        priority = web_request.get_int("priority", 0)

        if not profile:
            raise self.server.error("Profile name is required", 400)

        try:
            cmd = f'nmcli connection modify "{profile}" connection.autoconnect-priority {priority}'
            await self._run_nmcli_privileged(cmd)
            logging.info(f"WiFiManager: Set priority {priority} for {profile}")
            return {"status": "updated", "profile": profile, "priority": priority}
        except Exception as e:
            raise self.server.error(f"Failed to set priority: {e}", 500)

    async def _handle_ap_configure(self, web_request: WebRequest) -> Dict[str, Any]:
        """Configure Access Point settings."""
        ap_profile = web_request.get_str("profile", "AccessPopup")
        ssid = web_request.get_str("ssid", None)
        password = web_request.get_str("password", None)
        ip_address = web_request.get_str("ip", None)

        changes = []

        try:
            if ssid:
                await self._run_nmcli_privileged(
                    f'nmcli connection modify "{ap_profile}" wireless.ssid "{ssid}"'
                )
                changes.append(f"ssid={ssid}")

            if password:
                if len(password) < 8:
                    raise self.server.error("Password must be at least 8 characters", 400)
                await self._run_nmcli_privileged(
                    f'nmcli connection modify "{ap_profile}" wifi-sec.psk "{password}"'
                )
                changes.append("password=***")

            if ip_address:
                # Validate IP format (basic check)
                if not re.match(r'^\d+\.\d+\.\d+\.\d+/\d+$', ip_address):
                    raise self.server.error("Invalid IP format. Use CIDR notation: 192.168.50.5/24", 400)
                await self._run_nmcli_privileged(
                    f'nmcli connection modify "{ap_profile}" ipv4.addresses "{ip_address}" ipv4.method shared'
                )
                changes.append(f"ip={ip_address}")

            if not changes:
                raise self.server.error("No changes specified", 400)

            logging.info(f"WiFiManager: Updated AP config: {', '.join(changes)}")
            return {
                "status": "configured",
                "profile": ap_profile,
                "changes": changes
            }
        except self.server.error:
            raise
        except Exception as e:
            raise self.server.error(f"Failed to configure AP: {e}", 500)

    async def _handle_ap_get_config(self, web_request: WebRequest) -> Dict[str, Any]:
        """Get current Access Point configuration."""
        ap_profile = web_request.get_str("profile", "AccessPopup")

        try:
            # Get AP settings
            ok, result = await self._try_nmcli(
                f'nmcli -t connection show "{ap_profile}"',
                timeout=10.0
            )
            if not ok:
                logging.warning(
                    f"WiFiManager: AP profile {ap_profile} not found, returning empty config"
                )
                return {
                    "profile": ap_profile,
                    "ssid": None,
                    "ip": None,
                    "security": None
                }

            config = {
                "profile": ap_profile,
                "ssid": None,
                "ip": None,
                "security": None
            }

            for line in result.split('\n'):
                if ':' in line:
                    key, _, value = line.partition(':')
                    if key == 'wireless.ssid':
                        config["ssid"] = value
                    elif key == 'ipv4.addresses':
                        config["ip"] = value
                    elif key == 'wifi-sec.key-mgmt':
                        config["security"] = value

            return config
        except Exception as e:
            raise self.server.error(f"Failed to get AP config: {e}", 500)


def load_component(config: ConfigHelper) -> WiFiManager:
    return WiFiManager(config)

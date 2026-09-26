# StitchLabOS: WebSocket ping tuning for Moonraker
#
# Moonraker hardcodes Tornado's websocket_ping_interval (10 s) in
# components/application.py and exposes no config key for it. A browser
# whose radio parks briefly in AP mode misses a ping and is disconnected.
# See docs/runbooks/ap-troubleshooting.md Issue 5 and P0-11 of the
# Cross-Platform Mainsail Stability plan.
#
# This component sets both values in the Tornado application settings at
# startup instead of editing Moonraker's source: an edited tracked file
# makes update_manager refuse every Moonraker update ("repo has been
# modified"). Tornado reads the settings per connection, and Moonraker only
# starts listening after all components have loaded.
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..confighelper import ConfigHelper


class StitchlabWsTuning:
    def __init__(self, config: ConfigHelper) -> None:
        server = config.get_server()
        interval = config.getfloat("websocket_ping_interval", 30., above=0.)
        # Tornado >= 6.5 rejects a timeout longer than the interval.
        timeout = config.getfloat(
            "websocket_ping_timeout", 25., above=0., maxval=interval)

        app = server.lookup_component("application")
        try:
            settings = app.mutable_router.tornado_app.settings
        except AttributeError:
            logging.warning(
                "stitchlab_ws_tuning: Moonraker application layout changed, "
                "WebSocket ping settings left at Moonraker defaults")
            return
        if settings.get("websocket_ping_interval") is None:
            # Moonraker disables pings on Tornado < 6.5; keep that decision.
            logging.info("stitchlab_ws_tuning: WebSocket pings disabled "
                         "by Moonraker, nothing to tune")
            return
        settings["websocket_ping_interval"] = interval
        settings["websocket_ping_timeout"] = timeout
        logging.info(f"stitchlab_ws_tuning: WebSocket ping interval "
                     f"{interval:g} s, timeout {timeout:g} s")


def load_component(config: ConfigHelper) -> StitchlabWsTuning:
    return StitchlabWsTuning(config)

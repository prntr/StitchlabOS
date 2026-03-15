#!/bin/bash
# WiFi Status JSON Output for Moonraker API

active_conn=$(nmcli -t -f NAME,DEVICE connection show --active | grep wlan0 | cut -f1 -d:)

is_ap="false"
if [ -n "$active_conn" ]; then
    mode=$(nmcli connection show "$active_conn" 2>/dev/null | grep 'wireless.mode' | awk '{print $2}')
    if [ "$mode" = "ap" ]; then
        is_ap="true"
    fi
fi

ip_addr=$(nmcli -t connection show "$active_conn" 2>/dev/null | grep IP4.ADDRESS | cut -f2 -d: | cut -f1 -d/)
ssid=$(nmcli -t connection show "$active_conn" 2>/dev/null | grep wireless.ssid | cut -f2 -d:)

signal=0
if [ "$is_ap" = "false" ] && [ -n "$active_conn" ]; then
    signal=$(nmcli -f IN-USE,SIGNAL device wifi 2>/dev/null | grep "^\*" | awk '{print $2}')
    signal=${signal:-0}
fi

wifi_enabled=$(nmcli radio wifi)
[ "$wifi_enabled" = "enabled" ] && wifi_enabled="true" || wifi_enabled="false"

timer_active=$(systemctl is-active AccessPopup.timer 2>/dev/null)
[ "$timer_active" = "active" ] && timer_active="true" || timer_active="false"

status="disconnected"
if [ -n "$active_conn" ]; then
    [ "$is_ap" = "true" ] && status="ap_mode" || status="connected"
fi

cat <<EOF
{
  "status": "$status",
  "connection": {
    "name": "${active_conn:-null}",
    "ssid": "${ssid:-null}",
    "ip": "${ip_addr:-null}",
    "type": "wifi",
    "signal": ${signal},
    "is_ap": ${is_ap}
  },
  "wifi_enabled": ${wifi_enabled},
  "timer_active": ${timer_active}
}
EOF

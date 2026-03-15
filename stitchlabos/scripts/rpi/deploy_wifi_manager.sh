#!/bin/bash
# Deploy WiFi Manager to Raspberry Pi
# Usage: ./deploy_wifi_manager.sh --host pi@stitchlabdev.local

set -e

HOST=""
MOONRAKER_PATH="/home/pi/moonraker/moonraker/components"
SCRIPTS_PATH="/home/pi/printer_data/scripts"
CONFIG_PATH="/home/pi/printer_data/config"

while [[ $# -gt 0 ]]; do
    case $1 in
        --host) HOST="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [ -z "$HOST" ]; then
    echo "Usage: $0 --host user@hostname"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== Deploying WiFi Manager to $HOST ==="

# 1. Deploy wifi_manager.py
echo "Uploading wifi_manager.py..."
scp "$REPO_ROOT/config/moonraker/wifi_manager.py" "$HOST:$MOONRAKER_PATH/"

# 2. Deploy shell scripts
echo "Uploading WiFi scripts..."
ssh "$HOST" "mkdir -p $SCRIPTS_PATH"

# 2b. AP-mode DNS helpers (NetworkManager shared mode)
# Note: macOS treats `.local` as mDNS (multicast), so a unicast DNS override
# is not reliable there. We provide `stitchlabdev.lan` as the stable AP name.
echo "Configuring AP-mode DNS (dnsmasq-shared)..."
ssh "$HOST" "sudo mkdir -p /etc/NetworkManager/dnsmasq-shared.d"
ssh "$HOST" "cat | sudo tee /etc/NetworkManager/dnsmasq-shared.d/stitchlab-ap.conf > /dev/null" << 'CONF'
# StitchLab AP DNS overrides for NetworkManager `ipv4.method shared`
# AP IP is fixed by the AccessPopup profile (default: 192.168.50.5)
address=/stitchlabdev.lan/192.168.50.5
address=/stitchlabdev/192.168.50.5
# Included for non-macOS clients; macOS resolves `.local` via mDNS.
address=/stitchlabdev.local/192.168.50.5
CONF

# 2c. Avahi (mDNS) configuration
# Some clients cache/choose the first mDNS A record they see. If the Pi has more
# than one interface/address, Avahi may advertise multiple A records for
# `stitchlabdev.local`. In AP mode that can lead to clients resolving an address
# that is not reachable from the AP subnet.
#
# Fix: only advertise on wlan0 (both WiFi + AP use wlan0).
echo "Configuring Avahi (mDNS) to advertise on wlan0 only..."
ssh "$HOST" "sudo grep -q '^allow-interfaces=' /etc/avahi/avahi-daemon.conf \
    && sudo sed -i 's/^allow-interfaces=.*/allow-interfaces=wlan0/' /etc/avahi/avahi-daemon.conf \
    || sudo sed -i '/^use-ipv6=yes/a allow-interfaces=wlan0' /etc/avahi/avahi-daemon.conf"

# Ensure reflector is enabled (helps in some AP setups)
ssh "$HOST" "sudo sed -i 's/^#enable-reflector=no/enable-reflector=yes/' /etc/avahi/avahi-daemon.conf"
ssh "$HOST" "sudo systemctl restart avahi-daemon"

# Create wifi_status.sh
ssh "$HOST" "cat > $SCRIPTS_PATH/wifi_status.sh" << 'SCRIPT'
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
SCRIPT

# Create wifi_scan.sh
ssh "$HOST" "cat > $SCRIPTS_PATH/wifi_scan.sh" << 'SCRIPT'
#!/bin/bash
# WiFi Network Scanner JSON Output

saved_profiles=$(nmcli -t -f NAME connection show 2>/dev/null)

echo '{"networks": ['
first=true

nmcli -t -f SSID,SIGNAL,SECURITY,IN-USE device wifi list 2>/dev/null | while IFS=: read -r ssid signal security in_use; do
    [ -z "$ssid" ] && continue
    
    saved="false"
    echo "$saved_profiles" | grep -q "^${ssid}$" && saved="true"
    
    in_use_bool="false"
    [ "$in_use" = "*" ] && in_use_bool="true"
    
    if [ "$first" = true ]; then
        first=false
    else
        echo ","
    fi
    
    cat <<EOF
  {"ssid": "$ssid", "signal": ${signal:-0}, "security": "${security:-Open}", "in_use": ${in_use_bool}, "saved": ${saved}}
EOF
done

echo ']}'
SCRIPT

# Create wifi_profiles.sh
ssh "$HOST" "cat > $SCRIPTS_PATH/wifi_profiles.sh" << 'SCRIPT'
#!/bin/bash
# WiFi Saved Profiles JSON Output

echo '{"profiles": ['
first=true

nmcli -t -f AUTOCONNECT-PRIORITY,NAME,TYPE connection show 2>/dev/null | sort -nr | while IFS=: read -r priority name type; do
    [ -z "$name" ] && continue
    [ "$type" != "802-11-wireless" ] && continue
    
    mode=$(nmcli connection show "$name" 2>/dev/null | grep 'wireless.mode' | awk '{print $2}')
    mode=${mode:-infrastructure}
    
    profile_type="wifi"
    [ "$mode" = "ap" ] && profile_type="ap"
    
    ssid=$(nmcli connection show "$name" 2>/dev/null | grep 'wireless.ssid' | awk '{print $2}')
    
    autoconnect=$(nmcli connection show "$name" 2>/dev/null | grep 'connection.autoconnect:' | awk '{print $2}')
    autoconnect_bool="false"
    [ "$autoconnect" = "yes" ] && autoconnect_bool="true"
    
    if [ "$first" = true ]; then
        first=false
    else
        echo ","
    fi
    
    echo "  {\"name\": \"$name\", \"type\": \"$profile_type\", \"ssid\": \"$ssid\", \"autoconnect\": ${autoconnect_bool}, \"priority\": ${priority:-0}}"
done

echo ']}'
SCRIPT

# Make scripts executable
ssh "$HOST" "chmod +x $SCRIPTS_PATH/wifi_*.sh"

# 3. Add wifi_manager to moonraker.conf if not present
echo "Checking moonraker.conf..."
ssh "$HOST" "grep -q '\[wifi_manager\]' $CONFIG_PATH/moonraker.conf 2>/dev/null || echo -e '\n[wifi_manager]' >> $CONFIG_PATH/moonraker.conf"

# 4. Restart Moonraker
echo "Restarting Moonraker..."
ssh "$HOST" "sudo systemctl restart moonraker"

echo ""
echo "=== Deployment complete! ==="
echo "Test with: curl http://\$(echo $HOST | cut -d@ -f2):7125/server/wifi/status"

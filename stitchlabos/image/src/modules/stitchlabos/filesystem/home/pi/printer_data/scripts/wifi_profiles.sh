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

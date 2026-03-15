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

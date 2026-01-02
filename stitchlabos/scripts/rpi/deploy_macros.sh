#!/usr/bin/env bash
set -euo pipefail

# Deploy stitchlabos embroidery macros to a Raspberry Pi Klipper install.
#
# Usage:
#   ./deploy_macros.sh --host pi@raspberrypi.local [--config-dir ~/printer_data/config] [--restart]
#
# Notes:
# - This script is idempotent: it will not duplicate includes.
# - It creates timestamped backups of printer.cfg before editing.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MACROS_SRC="$ROOT_DIR/config/klipper/embroidery_macros.cfg"

HOST=""
CONFIG_DIR="~/printer_data/config"
RESTART=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="$2"; shift 2 ;;
    --config-dir)
      CONFIG_DIR="$2"; shift 2 ;;
    --restart)
      RESTART=1; shift ;;
    -h|--help)
      sed -n '1,120p' "$0"; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2 ;;
  esac
done

if [[ -z "$HOST" ]]; then
  echo "Missing --host (e.g. --host pi@raspberrypi.local)" >&2
  exit 2
fi

if [[ ! -f "$MACROS_SRC" ]]; then
  echo "Macros source not found: $MACROS_SRC" >&2
  exit 1
fi

echo "Deploying macros to $HOST:$CONFIG_DIR ..."

# Upload to a stable temp location first (avoids tilde-expansion quirks in scp).
scp "$MACROS_SRC" "$HOST:/tmp/embroidery_macros.cfg"

# Move into place + ensure printer.cfg includes the file.
ssh "$HOST" "CONFIG_DIR='$CONFIG_DIR' bash -s" <<'EOF'
set -euo pipefail

# Expand a leading ~ to remote $HOME if present.
CFG_DIR="${CONFIG_DIR/#\~/$HOME}"
mkdir -p "$CFG_DIR"

install -m 0644 /tmp/embroidery_macros.cfg "$CFG_DIR/embroidery_macros.cfg"

PRINTER_CFG="$CFG_DIR/printer.cfg"
INCLUDE_LINE='[include embroidery_macros.cfg]'

if [[ ! -f "$PRINTER_CFG" ]]; then
  echo "printer.cfg not found at $PRINTER_CFG" >&2
  exit 1
fi

TS="$(date +%Y%m%d-%H%M%S)"
cp "$PRINTER_CFG" "$PRINTER_CFG.bak.$TS"

if grep -Fqx "$INCLUDE_LINE" "$PRINTER_CFG"; then
  echo "Include already present in printer.cfg"
else
  # Insert include near top (after initial comment/header block).
  awk -v inc="$INCLUDE_LINE" '
    BEGIN{added=0}
    {print}
    NR==1{next}
    !added && $0=="" {print inc; added=1}
    END{if(!added) print "\n" inc}
  ' "$PRINTER_CFG" > "$PRINTER_CFG.tmp"
  mv "$PRINTER_CFG.tmp" "$PRINTER_CFG"
  echo "Inserted include into printer.cfg"
fi
EOF

if [[ "$RESTART" -eq 1 ]]; then
  echo "Restarting klipper on $HOST ..."
  ssh "$HOST" "sudo systemctl restart klipper"
fi

echo "Done. If you didn't pass --restart, restart Klipper manually."
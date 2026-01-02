#!/usr/bin/env bash
set -euo pipefail

# Build the local Mainsail fork and deploy its dist/ to the Raspberry Pi's Mainsail web root.
#
# Usage:
#   ./deploy_mainsail_dist.sh --host pi@raspberrypi.local --webroot /var/www/mainsail
#   ./deploy_mainsail_dist.sh --host pi@raspberrypi.local --webroot /usr/share/mainsail
#
# This is intentionally conservative: it makes a backup tarball on the Pi before syncing.

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MAINSAIL_DIR="$WORKSPACE_ROOT/mainsail"

HOST=""
WEBROOT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="$2"; shift 2 ;;
    --webroot)
      WEBROOT="$2"; shift 2 ;;
    -h|--help)
      sed -n '1,160p' "$0"; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2 ;;
  esac
done

if [[ -z "$HOST" || -z "$WEBROOT" ]]; then
  echo "Missing --host and/or --webroot" >&2
  exit 2
fi

if [[ ! -d "$MAINSAIL_DIR" ]]; then
  echo "Mainsail directory not found: $MAINSAIL_DIR" >&2
  exit 1
fi

echo "Building Mainsail locally..."
cd "$MAINSAIL_DIR"
# use lockfile for reproducibility
npm ci
npm run build

DIST_DIR="$MAINSAIL_DIR/dist"
if [[ ! -d "$DIST_DIR" ]]; then
  echo "dist/ not found after build" >&2
  exit 1
fi

echo "Uploading dist/ to Pi (/tmp/mainsail-dist)..."
rsync -a --delete "$DIST_DIR/" "$HOST:/tmp/mainsail-dist/"

echo "Creating backup and deploying into webroot on Pi ($HOST)..."
ssh "$HOST" "WEBROOT='$WEBROOT' bash -s" <<'EOF'
set -euo pipefail

if [[ ! -d "$WEBROOT" ]]; then
  echo "Webroot does not exist: $WEBROOT" >&2
  exit 1
fi

TS="$(date +%Y%m%d-%H%M%S)"
BACKUP="/tmp/mainsail-webroot-backup-$TS.tar.gz"

if [[ -w "$WEBROOT" ]]; then
  tar -C "$WEBROOT" -czf "$BACKUP" .
  echo "Backup written to $BACKUP"
  rsync -a --delete /tmp/mainsail-dist/ "$WEBROOT/"
  echo "Deploy complete (no sudo)"
else
  if sudo -n true 2>/dev/null; then
    sudo tar -C "$WEBROOT" -czf "$BACKUP" .
    echo "Backup written to $BACKUP"
    sudo rsync -a --delete /tmp/mainsail-dist/ "$WEBROOT/"
    echo "Deploy complete (sudo)"
  else
    echo 'Webroot is not writable and passwordless sudo is not available.' >&2
    echo 'Either run this script interactively with sudo password, or use a writable webroot.' >&2
    exit 1
  fi
fi
EOF

echo "Done. You may need a hard-refresh (PWA cache)."
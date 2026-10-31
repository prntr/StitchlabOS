#!/usr/bin/env bash
# Klipper drift check (make klipper-drift): runs our printer.cfg variants,
# embroidery_macros.cfg, mainsail.cfg and the sample jobs in samples/
# through klippy batch mode at the release's pin and at upstream master,
# and lists the upstream changes in between. Needs Docker and network.
#
# Environment (all optional):
#   KLIPPER_DRIFT_OUT      report folder (default .local/klipper-drift/<UTC time>)
#   KLIPPER_DRIFT_CACHE    mirrors, dictionaries, venvs (default .local/klipper-drift/cache)
#   KLIPPER_DRIFT_COMPARE  upstream Klipper ref to compare with (default master)
#   KLIPPER_DRIFT_PIN      Klipper commit to treat as the pin (default KLIPPER_REF
#                          of upstream-pins.conf), e.g. to try a pin move
#   KLIPPER_DRIFT_MACROS   an embroidery_macros.cfg to use instead of the one
#                          at the stitchlabos-config commit this repo pins
#   KLIPPER_DRIFT_EXTRA    more printer.cfg variants, "name=/path/printer.cfg ...";
#                          for local files that must not enter the repo
# Exit status 1 when a sample does not behave as its header expects at the pin.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
out="${KLIPPER_DRIFT_OUT:-$repo/.local/klipper-drift/$(date -u +%Y%m%dT%H%M%SZ)}"
cache="${KLIPPER_DRIFT_CACHE:-$repo/.local/klipper-drift/cache}"
compare="${KLIPPER_DRIFT_COMPARE:-master}"
pins="$repo/stitchlabos/image/upstream-pins.conf"
image_cfg="$repo/stitchlabos/image/src/modules/klipper/filesystem/home/pi/printer_data/config/printer.cfg"

pin() { grep -E "^$1=[0-9a-f]{40}$" "$pins" | cut -d= -f2; }
klipper_ref="${KLIPPER_DRIFT_PIN:-$(pin KLIPPER_REF)}"
mainsail_config_ref="$(pin MAINSAIL_CONFIG_REF)"

mkdir -p "$out" "$cache/mirrors" "$cache/build"

mirror() {   # name url
    local dir="$cache/mirrors/$1.git"
    if [ -d "$dir" ]; then
        git -C "$dir" fetch --quiet --prune --tags origin '+refs/heads/*:refs/heads/*'
    else
        git clone --quiet --mirror "$2" "$dir"
    fi
}
mirror klipper https://github.com/Klipper3d/klipper.git
mirror mainsail-config https://github.com/mainsail-crew/mainsail-config.git

# mainsail.cfg at a ref; in mainsail-config it is a symlink to client.cfg.
mainsail_cfg() {
    local dir="$cache/mirrors/mainsail-config.git" ref=$1 mode target
    mode="$(git -C "$dir" ls-tree "$ref" mainsail.cfg | awk '{print $1}')"
    if [ "$mode" = "120000" ]; then
        target="$(git -C "$dir" show "$ref:mainsail.cfg")"
        git -C "$dir" show "$ref:${target#./}"
    else
        git -C "$dir" show "$ref:mainsail.cfg"
    fi
}

if [ -n "${KLIPPER_DRIFT_MACROS:-}" ]; then
    macros_source="$KLIPPER_DRIFT_MACROS"
    cp "$KLIPPER_DRIFT_MACROS" "$out/embroidery_macros.cfg"
else
    config_pin="$(git -C "$repo" ls-tree HEAD stitchlabos-config | awk '{print $3}')"
    mirror stitchlabos-config https://github.com/prntr/stitchlabos-config.git
    git -C "$cache/mirrors/stitchlabos-config.git" show \
        "$config_pin:printer_data/config/embroidery_macros.cfg" > "$out/embroidery_macros.cfg"
    macros_source="prntr/stitchlabos-config@${config_pin:0:12} (submodule pin)"
fi

for side in pin compare; do
    dir="$out/inputs/$side"
    mkdir -p "$dir"
    cp "$image_cfg" "$dir/printer.cfg"
    cp "$out/embroidery_macros.cfg" "$dir/embroidery_macros.cfg"
    if [ "$side" = pin ]; then ref="$mainsail_config_ref"; else ref=master; fi
    mainsail_cfg "$ref" > "$dir/mainsail.cfg"
    for spec in ${KLIPPER_DRIFT_EXTRA:-}; do
        mkdir -p "$dir/extra/${spec%%=*}"
        cp "${spec#*=}" "$dir/extra/${spec%%=*}/printer.cfg"
    done
done

echo "Klipper drift check: pin ${klipper_ref:0:12} vs $compare; macros from $macros_source"
docker build --quiet --tag stitchlab-klipper-drift "$here" >/dev/null
status=0
docker run --rm \
    --volume "$cache/mirrors:/mirrors:ro" \
    --volume "$here:/drift:ro" \
    --volume "$repo/firmware:/firmware:ro" \
    --volume "$out:/out" \
    --volume "$cache/build:/cache" \
    --env UV_CACHE_DIR=/cache/uv \
    stitchlab-klipper-drift \
    uv run --no-project --python /usr/bin/python3 /drift/drift.py \
        --klipper-mirror /mirrors/klipper.git --pin "$klipper_ref" --compare "$compare" \
        --mainsail-config-mirror /mirrors/mainsail-config.git \
        --mainsail-config-pin "$mainsail_config_ref" \
        --inputs /out/inputs --drift-dir /drift \
        --firmware-config /firmware/skr-pico/klipper.config \
        --cache /cache --out /out || status=$?
rm -rf "$out/inputs"
printf 'Macros: %s\n' "$macros_source" >> "$out/report.md"
echo "Report: $out/report.md"
exit "$status"

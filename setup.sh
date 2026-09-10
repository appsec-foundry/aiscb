#!/bin/sh
# Guided install and update from a checkout or a temporary remote bundle.
# POSIX sh, so `sh setup.sh` works too.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
script_name=${0##*/}
if [ "$script_name" = "setup.sh" ] \
    && [ -f "$script_dir/scripts/install.py" ] \
    && [ -f "$script_dir/scripts/show_baseline_version.py" ] \
    && [ -f "$script_dir/secure-coding-baseline.md" ]; then
    cd "$script_dir"
    exec python3 scripts/install.py --interactive "$@"
fi

command -v curl >/dev/null 2>&1 || {
    echo "curl is required for setup without a checkout." >&2
    exit 1
}
command -v python3 >/dev/null 2>&1 || {
    echo "python3 is required for setup." >&2
    exit 1
}
command -v sha256sum >/dev/null 2>&1 || {
    echo "sha256sum is required for verified setup." >&2
    exit 1
}

# This tag is never moved or reused. The hashes keep a moved or corrupted tag
# from changing what this reviewed bootstrap executes.
bundle_ref="aiscb-bundle-0.1.14-6"
baseline_sha="a6fc88833aaae7f9e5e1ff9ebe4ba152e56660e743c75094b56b8b25968bfeb2"
installer_sha="d9878b02958cfb98524313e368cd7201a7baadef27b44fa49e22b2d762c4469a"
helper_sha="b2fa3d5d1d9d891117ca9b035db243129d24b6eb0c2c54c3568eef623f83bdea"

setup_tmp=$(mktemp -d "${TMPDIR:-/tmp}/aiscb-setup.XXXXXX")
cleanup() {
    if [ -d "$setup_tmp" ]; then
        rm -r -- "$setup_tmp"
    fi
}
trap cleanup 0 1 2 3 15
mkdir -p "$setup_tmp/scripts"

source_root="https://raw.githubusercontent.com/appsec-foundry/aiscb/$bundle_ref"
download() {
    bundle_path=$1
    expected_sha=$2
    max_bytes=$3
    destination="$setup_tmp/$bundle_path"
    curl --proto '=https' \
        --fail --silent --show-error --max-time 30 --max-filesize "$max_bytes" \
        --output "$destination" "$source_root/$bundle_path"
    actual_size=$(wc -c < "$destination")
    if [ "$actual_size" -gt "$max_bytes" ]; then
        echo "Downloaded $bundle_path exceeds its size limit." >&2
        exit 2
    fi
    if ! printf '%s  %s\n' "$expected_sha" "$destination" |
        sha256sum --check >/dev/null 2>&1; then
        echo "Integrity check failed for $bundle_path." >&2
        exit 2
    fi
}

download secure-coding-baseline.md "$baseline_sha" 262144
download scripts/install.py "$installer_sha" 524288
download scripts/show_baseline_version.py "$helper_sha" 262144

python3 "$setup_tmp/scripts/install.py" --interactive --offline "$@"

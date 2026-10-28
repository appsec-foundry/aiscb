#!/bin/sh
# Generated bootstrap: exact release assets, checked before executing any code.
set -eu
command -v curl >/dev/null 2>&1
command -v python3 >/dev/null 2>&1
command -v sha256sum >/dev/null 2>&1
source_root="https://github.com/appsec-foundry/aiscb/releases/download/aiscb-bundle-0.1.21-1"
setup_tmp=$(mktemp -d "${TMPDIR:-/tmp}/aiscb-setup.XXXXXX")
cleanup() { if [ -d "$setup_tmp" ]; then rm -r -- "$setup_tmp"; fi; }
trap cleanup 0 1 2 3 15
mkdir -p "$setup_tmp/scripts"
download() {
    bundle_path=$1
    expected_sha=$2
    max_bytes=$3
    destination="$setup_tmp/$bundle_path"
    curl --proto '=https' --proto-redir '=https' --location \
        --fail --silent --show-error --max-time 30 --max-filesize "$max_bytes" \
        --output "$destination" "$source_root/${bundle_path##*/}"
    actual_size=$(wc -c < "$destination")
    if [ "$actual_size" -gt "$max_bytes" ]; then
        echo "Downloaded $bundle_path exceeds its size limit." >&2
        exit 2
    fi
    if ! printf '%s  %s\n' "$expected_sha" "$destination" | sha256sum --check >/dev/null 2>&1; then
        echo "Integrity check failed for $bundle_path." >&2
        exit 2
    fi
}
download secure-coding-baseline.md "696c044f9393856e069448365e7f950371206c16a63f057b18396f0fe592c5ef" 262144
download scripts/install.py "c2e01640898e10cd4846f15b10c6d60aa5a260ffaaee2871362bfbddbf9bfb84" 524288
download scripts/show_baseline_version.py "af2c4b13698fe84ca78332fef51849f8b42d08a8c5ef3c753d4e0165bea05df6" 262144
python3 "$setup_tmp/scripts/install.py" --interactive --offline "$@"

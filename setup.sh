#!/bin/sh
# Generated bootstrap: exact release assets, checked before executing any code.
set -eu
command -v curl >/dev/null 2>&1
command -v python3 >/dev/null 2>&1
command -v sha256sum >/dev/null 2>&1
source_root="https://github.com/appsec-foundry/aiscb/releases/download/aiscb-bundle-0.1.18-2"
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
download secure-coding-baseline.md "15f3306a83b5f4e4075ece79608ad5c73a6c2f8cc0596c4926e552a40f9dd0af" 262144
download scripts/install.py "9a58a60ff731f7af1c46dfd7f35aebed55cbf95b0a2e02cc2dec037cd9d6cce5" 524288
download scripts/show_baseline_version.py "45fcef85aedc66f2d5e06157b11fb9294ae5e7506581c5448d9a02ffa33ebe46" 262144
python3 "$setup_tmp/scripts/install.py" --interactive --offline "$@"

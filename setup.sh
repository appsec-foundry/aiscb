#!/bin/sh
# Generated bootstrap: exact release assets, checked before executing any code.
set -eu
command -v curl >/dev/null 2>&1
command -v python3 >/dev/null 2>&1
command -v sha256sum >/dev/null 2>&1
source_root="https://github.com/appsec-foundry/aiscb/releases/download/aiscb-bundle-0.1.19-1"
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
download secure-coding-baseline.md "be68be5b2c9653441e6a65812bb993a5858dfffe295c5917fce9b8e158a286fa" 262144
download scripts/install.py "e48cc66c7d274ff9307025e18955644a4ac45727a3bed42a49882d5e4b117142" 524288
download scripts/show_baseline_version.py "45fcef85aedc66f2d5e06157b11fb9294ae5e7506581c5448d9a02ffa33ebe46" 262144
python3 "$setup_tmp/scripts/install.py" --interactive --offline "$@"

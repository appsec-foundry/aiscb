#!/bin/sh
# Generated bootstrap: exact release assets, checked before executing any code.
set -eu
command -v curl >/dev/null 2>&1
command -v python3 >/dev/null 2>&1
command -v sha256sum >/dev/null 2>&1
source_root="https://github.com/appsec-foundry/aiscb/releases/download/aiscb-bundle-0.1.16-1"
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
download secure-coding-baseline.md "979a42d0c95d06491e9b21bd2a89c896d1aedb2dbb06f1ad585805d9c6be04b5" 262144
download scripts/install.py "1b40da95dd68eee0125f9f75a0c5201349f32851edccd3f151bd8185d0a377a0" 524288
download scripts/show_baseline_version.py "2b4c6d1f85b76294169d1b958bc2b0a98da6952b6b9768c99823cb2d7582cec5" 262144
python3 "$setup_tmp/scripts/install.py" --interactive --offline "$@"

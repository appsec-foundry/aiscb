#!/bin/sh
# Generated bootstrap: exact release assets, checked before executing any code.
set -eu
command -v curl >/dev/null 2>&1
command -v python3 >/dev/null 2>&1
command -v sha256sum >/dev/null 2>&1
source_root="https://github.com/appsec-foundry/aiscb/releases/download/aiscb-bundle-0.1.17-1"
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
download secure-coding-baseline.md "0ac62aec99bb760669427c8e0f7937413392668111f2610ff8a22dcb786a6ca0" 262144
download scripts/install.py "37e94e0e495c4a2fa8fb52ea4ad742e9a58a8ee6d4426224af19ba953fb74edb" 524288
download scripts/show_baseline_version.py "2b4c6d1f85b76294169d1b958bc2b0a98da6952b6b9768c99823cb2d7582cec5" 262144
python3 "$setup_tmp/scripts/install.py" --interactive --offline "$@"

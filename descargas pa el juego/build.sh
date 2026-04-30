#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
OUT_DIR="$SCRIPT_DIR"
APP_NAME="Raven"
ENTRY="$ROOT_DIR/main.py"
ASSETS="$ROOT_DIR/Game/assets"

cd "$ROOT_DIR"

python3 -m pip install --quiet --upgrade pyinstaller pygame

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

build_unix_binary () {
    local target_label="$1"
    local out_subdir="$WORK_DIR/$target_label"
    rm -rf "$out_subdir"
    mkdir -p "$out_subdir"
    pyinstaller \
        --noconfirm \
        --clean \
        --onefile \
        --windowed \
        --name "$APP_NAME" \
        --add-data "$ASSETS:Game/assets" \
        --distpath "$out_subdir/dist" \
        --workpath "$out_subdir/build" \
        --specpath "$out_subdir" \
        "$ENTRY"
    echo "$out_subdir/dist/$APP_NAME"
}

build_appimage () {
    echo ">>> Building Linux AppImage"
    local bin_path
    bin_path="$(build_unix_binary linux)"

    if ! command -v appimagetool >/dev/null 2>&1; then
        local tool="$WORK_DIR/appimagetool"
        local arch
        arch="$(uname -m)"
        curl -L -o "$tool" \
            "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${arch}.AppImage"
        chmod +x "$tool"
        APPIMAGETOOL="$tool"
    else
        APPIMAGETOOL="$(command -v appimagetool)"
    fi

    local app_dir="$WORK_DIR/${APP_NAME}.AppDir"
    rm -rf "$app_dir"
    mkdir -p "$app_dir/usr/bin"
    cp "$bin_path" "$app_dir/usr/bin/$APP_NAME"

    cat > "$app_dir/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/Raven" "$@"
EOF
    chmod +x "$app_dir/AppRun"

    cat > "$app_dir/${APP_NAME}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=${APP_NAME}
Exec=${APP_NAME}
Icon=${APP_NAME}
Categories=Game;
EOF

    if [ -f "$ASSETS/UI/icon.png" ]; then
        cp "$ASSETS/UI/icon.png" "$app_dir/${APP_NAME}.png"
    else
        python3 - "$app_dir/${APP_NAME}.png" <<'EOF'
import sys, struct, zlib
path = sys.argv[1]
def chunk(t, d):
    return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
sig = b"\x89PNG\r\n\x1a\n"
ihdr = struct.pack(">IIBBBBB", 256, 256, 8, 2, 0, 0, 0)
raw = b"".join(b"\x00" + b"\x10\x10\x10" * 256 for _ in range(256))
idat = zlib.compress(raw, 9)
with open(path, "wb") as f:
    f.write(sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b""))
EOF
    fi

    ARCH="$(uname -m)" "$APPIMAGETOOL" "$app_dir" "$OUT_DIR/${APP_NAME}.AppImage"
    chmod +x "$OUT_DIR/${APP_NAME}.AppImage"
    echo ">>> Wrote $OUT_DIR/${APP_NAME}.AppImage"
}

build_app () {
    echo ">>> Building macOS .app"
    if [ "$(uname -s)" = "Darwin" ]; then
        local out_subdir="$WORK_DIR/macos"
        mkdir -p "$out_subdir"
        pyinstaller \
            --noconfirm \
            --clean \
            --windowed \
            --name "$APP_NAME" \
            --add-data "$ASSETS:Game/assets" \
            --distpath "$out_subdir/dist" \
            --workpath "$out_subdir/build" \
            --specpath "$out_subdir" \
            "$ENTRY"
        rm -rf "$OUT_DIR/${APP_NAME}.app"
        cp -R "$out_subdir/dist/${APP_NAME}.app" "$OUT_DIR/${APP_NAME}.app"
        echo ">>> Wrote $OUT_DIR/${APP_NAME}.app"
        return
    fi

    local bin_path
    bin_path="$(build_unix_binary macos-fallback)"
    local app_path="$OUT_DIR/${APP_NAME}.app"
    rm -rf "$app_path"
    mkdir -p "$app_path/Contents/MacOS" "$app_path/Contents/Resources"
    cp "$bin_path" "$app_path/Contents/MacOS/$APP_NAME"
    chmod +x "$app_path/Contents/MacOS/$APP_NAME"
    cat > "$app_path/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key><string>${APP_NAME}</string>
    <key>CFBundleIdentifier</key><string>com.raven.game</string>
    <key>CFBundleName</key><string>${APP_NAME}</string>
    <key>CFBundleDisplayName</key><string>${APP_NAME}</string>
    <key>CFBundleVersion</key><string>1.0</string>
    <key>CFBundleShortVersionString</key><string>1.0</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
EOF
    echo ">>> Wrote $OUT_DIR/${APP_NAME}.app (Linux-built fallback bundle; rebuild on macOS for a signed binary)"
}

build_exe () {
    echo ">>> Building Windows .exe"
    if [ "$(uname -s | cut -c1-5)" = "MINGW" ] || [ "$(uname -s | cut -c1-6)" = "CYGWIN" ] || [ "${OS:-}" = "Windows_NT" ]; then
        local out_subdir="$WORK_DIR/windows"
        mkdir -p "$out_subdir"
        pyinstaller \
            --noconfirm \
            --clean \
            --onefile \
            --windowed \
            --name "$APP_NAME" \
            --add-data "$ASSETS;Game/assets" \
            --distpath "$out_subdir/dist" \
            --workpath "$out_subdir/build" \
            --specpath "$out_subdir" \
            "$ENTRY"
        cp "$out_subdir/dist/${APP_NAME}.exe" "$OUT_DIR/${APP_NAME}.exe"
        echo ">>> Wrote $OUT_DIR/${APP_NAME}.exe"
        return
    fi

    if ! command -v wine >/dev/null 2>&1; then
        echo "!! 'wine' not installed; skipping .exe. Install wine + a Windows python and rerun, or run this script on Windows." >&2
        return
    fi

    local wine_python="${WINE_PYTHON:-python.exe}"
    local out_subdir="$WORK_DIR/windows"
    mkdir -p "$out_subdir"
    wine "$wine_python" -m pip install --quiet pyinstaller pygame
    wine "$wine_python" -m PyInstaller \
        --noconfirm \
        --clean \
        --onefile \
        --windowed \
        --name "$APP_NAME" \
        --add-data "$ASSETS;Game/assets" \
        --distpath "$out_subdir/dist" \
        --workpath "$out_subdir/build" \
        --specpath "$out_subdir" \
        "$ENTRY"
    cp "$out_subdir/dist/${APP_NAME}.exe" "$OUT_DIR/${APP_NAME}.exe"
    echo ">>> Wrote $OUT_DIR/${APP_NAME}.exe"
}

TARGETS="${*:-all}"

case "$TARGETS" in
    all)
        build_appimage
        build_app
        build_exe
        ;;
    *)
        for t in $TARGETS; do
            case "$t" in
                appimage|AppImage|linux) build_appimage ;;
                app|macos|mac) build_app ;;
                exe|windows|win) build_exe ;;
                *) echo "Unknown target: $t (use: appimage, app, exe, or all)" >&2; exit 1 ;;
            esac
        done
        ;;
esac

echo ""
echo "Build outputs in $OUT_DIR :"
ls -la "$OUT_DIR" | grep -v '^total' | grep -v '^d' || true

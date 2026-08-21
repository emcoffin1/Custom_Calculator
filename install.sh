#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"
DESKTOP_DIR="$DATA_HOME/applications"
DESKTOP_FILE="$DESKTOP_DIR/conversions-calculator.desktop"

if [[ "${1:-}" == "--install-deps" ]]; then
    if ! command -v apt-get >/dev/null 2>&1; then
        echo "Automatic dependency installation currently supports apt-based distributions." >&2
        echo "Install Python 3, PyGObject, GTK 3, and WebKitGTK 4.1 bindings with your package manager." >&2
        exit 1
    fi
    sudo apt-get update
    if apt-cache show gir1.2-webkit2-4.1 >/dev/null 2>&1; then
        webkit_package=gir1.2-webkit2-4.1
    else
        webkit_package=gir1.2-webkit2-4.0
    fi
    sudo apt-get install -y python3 python3-gi gir1.2-gtk-3.0 "$webkit_package"
fi

if ! "$APP_DIR/launch.sh" --diagnostics >/dev/null 2>&1; then
    echo "Runtime dependency check failed. Run: $APP_DIR/install.sh --install-deps" >&2
    exit 1
fi

mkdir -p "$DESKTOP_DIR" "$BIN_HOME"
escaped_dir=${APP_DIR//&/\\&}
sed "s&@APP_DIR@&$escaped_dir&g" "$APP_DIR/conversions-calculator.desktop.in" > "$DESKTOP_FILE"
chmod 0644 "$DESKTOP_FILE"
ln -sfn "$APP_DIR/launch.sh" "$BIN_HOME/conversions-calculator"
if command -v update-desktop-database >/dev/null 2>&1; then update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true; fi

echo "Installed desktop entry: $DESKTOP_FILE"
echo "Installed command: $BIN_HOME/conversions-calculator"
echo "Assign 'Conversions Calculator' to a global shortcut in your desktop settings."

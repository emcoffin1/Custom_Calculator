#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
    echo "conversions-calculator: python3 is required" >&2
    exit 1
fi
if ! python3 -c "import gi; gi.require_version('Gtk','3.0'); gi.require_version('WebKit2','4.1')" >/dev/null 2>&1; then
    echo "conversions-calculator: GTK 3 and WebKitGTK 4.1 Python bindings are required." >&2
    echo "On Mint, Ubuntu, KDE neon, or Kubuntu run: ./install.sh --install-deps" >&2
    exit 1
fi
exec python3 "$APP_DIR/app.py" "$@"

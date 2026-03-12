#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

ICON_SOURCE="$ROOT_DIR/assets/icon.svg"
ICON_TARGET_DIR="$HOME/.local/share/icons"
ICON_TARGET="$ICON_TARGET_DIR/vscode-insiders-updater.svg"
LEGACY_ICON_PNG="$HOME/.local/share/icons/vscode-insiders-installer.png"
LEGACY_ICON_SVG="$HOME/.local/share/icons/vscode-insiders-installer.svg"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/vscode-insiders-updater.desktop"
RUNNER_SCRIPT="$ROOT_DIR/scripts/run-installer-ui.sh"

if [[ ! -f "$ICON_SOURCE" ]]; then
  echo "Icon not found at: $ICON_SOURCE"
  exit 1
fi

mkdir -p "$ICON_TARGET_DIR" "$DESKTOP_DIR"
cp -f "$ICON_SOURCE" "$ICON_TARGET"
rm -f "$LEGACY_ICON_PNG" "$LEGACY_ICON_SVG"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=VS Code Insiders Updater
GenericName=VS Code Insiders Updater
Comment=Professional VS Code Insiders updater and installer
Exec=/bin/bash $RUNNER_SCRIPT
Icon=$ICON_TARGET
Terminal=false
Categories=Development;Utility;
Keywords=vscode;insiders;updater;
StartupNotify=true
StartupWMClass=vscode-insiders-updater
EOF

chmod +x "$RUNNER_SCRIPT"
chmod +x "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" || true
fi

echo "Launcher created at: $DESKTOP_FILE"
echo "Pin it to the Ubuntu dock via Activities -> search -> right-click -> Add to Favorites."

#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "This helper must run as root."
  exit 1
fi

if [[ "${1:-}" == "--check" ]]; then
  command -v dpkg >/dev/null 2>&1
  command -v apt-get >/dev/null 2>&1
  exit 0
fi

DEB_PATH="${1:-}"
if [[ -z "$DEB_PATH" ]]; then
  echo "Usage: $0 /path/to/vscode-insiders.deb"
  exit 1
fi

if [[ ! -f "$DEB_PATH" ]]; then
  echo "File not found: $DEB_PATH"
  exit 1
fi

if ! dpkg -i "$DEB_PATH"; then
  apt-get -f install -y
fi

echo "VS Code Insiders installation finished."

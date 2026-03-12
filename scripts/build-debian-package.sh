#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if ! command -v dpkg-buildpackage >/dev/null 2>&1; then
  echo "dpkg-buildpackage is required. Install: sudo apt install -y build-essential devscripts debhelper dh-python pybuild-plugin-pyproject"
  exit 1
fi

cd "$ROOT_DIR"
dpkg-buildpackage -us -uc -b

echo "Build complete. Debian artifacts are in: $(dirname "$ROOT_DIR")"

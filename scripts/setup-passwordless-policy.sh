#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo /bin/bash "$0" "$@"
fi

TARGET_USER="${SUDO_USER:-${USER:-}}"
if [[ -z "$TARGET_USER" ]]; then
  echo "Unable to determine target user. Run with sudo from your account."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPER_SCRIPT="$SCRIPT_DIR/system-install-helper.sh"
SUDOERS_FILE="/etc/sudoers.d/vscode-insiders-updater"

if [[ ! -f "$HELPER_SCRIPT" ]]; then
  echo "Helper script not found at: $HELPER_SCRIPT"
  exit 1
fi

cat > "$SUDOERS_FILE" <<EOF
$TARGET_USER ALL=(root) NOPASSWD: /bin/bash $HELPER_SCRIPT *
EOF

chmod 440 "$SUDOERS_FILE"

if command -v visudo >/dev/null 2>&1; then
  visudo -cf "$SUDOERS_FILE"
fi

echo "Passwordless policy configured for user: $TARGET_USER"

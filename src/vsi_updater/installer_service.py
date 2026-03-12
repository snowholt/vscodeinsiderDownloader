"""Install orchestration and dock identity fixes for VS Code Insiders."""

from __future__ import annotations

import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

from vsi_updater.models import InstallResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HELPER_CANDIDATES = [
    PROJECT_ROOT / "scripts" / "system-install-helper.sh",
    Path("/usr/lib/vscode-insiders-updater/system-install-helper.sh"),
]
SETUP_CANDIDATES = [
    PROJECT_ROOT / "scripts" / "setup-passwordless-policy.sh",
    Path("/usr/lib/vscode-insiders-updater/setup-passwordless-policy.sh"),
]
USER_AGENT = "vscode-insiders-updater/0.1"


class InstallerService:
    """Install service that supports one-time policy bootstrap and no-prompt updates."""

    def _resolve_existing(self, candidates: List[Path]) -> Optional[Path]:
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    def is_passwordless_ready(self) -> bool:
        helper_script = self._resolve_existing(HELPER_CANDIDATES)
        if not helper_script:
            return False
        result = self._run(["sudo", "-n", "/bin/bash", str(helper_script), "--check"])
        return result.returncode == 0

    def configure_passwordless_policy(self) -> InstallResult:
        if self.is_passwordless_ready():
            return InstallResult(True, "Passwordless policy is already configured.")

        setup_script = self._resolve_existing(SETUP_CANDIDATES)
        if not setup_script:
            return InstallResult(
                False,
                "Policy setup script is missing.",
                "Expected one of: " + ", ".join(str(path) for path in SETUP_CANDIDATES),
            )

        if self._run(["which", "pkexec"]).returncode == 0:
            cmd = ["pkexec", "/bin/bash", str(setup_script)]
        else:
            cmd = ["sudo", "/bin/bash", str(setup_script)]

        result = self._run(cmd)
        if result.returncode == 0:
            return InstallResult(True, "Passwordless policy configured successfully.")

        details = (result.stderr or result.stdout).strip()
        return InstallResult(False, "Failed to configure passwordless policy.", details)

    def _download_deb(self, download_url: str) -> Tuple[Optional[Path], Optional[InstallResult]]:
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".deb")
        tmp_file.close()
        target = Path(tmp_file.name)

        request = urllib.request.Request(download_url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30) as response, target.open("wb") as out:
                out.write(response.read())
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
            return None, InstallResult(False, "Download failed.", str(exc))

        return target, None

    def install_update(self, download_url: str) -> InstallResult:
        helper_script = self._resolve_existing(HELPER_CANDIDATES)
        if not helper_script:
            return InstallResult(
                False,
                "System install helper script is missing.",
                "Expected one of: " + ", ".join(str(path) for path in HELPER_CANDIDATES),
            )

        setup_script = self._resolve_existing(SETUP_CANDIDATES)

        if not self.is_passwordless_ready():
            return InstallResult(
                False,
                "Passwordless policy is not configured yet.",
                (
                    "Run the one-time setup first: "
                    f"/bin/bash {setup_script}" if setup_script else "Setup script not found."
                ),
            )

        deb_path, error = self._download_deb(download_url)
        if error:
            return error

        try:
            result = self._run(["sudo", "-n", "/bin/bash", str(helper_script), str(deb_path)])
            if result.returncode == 0:
                self.ensure_code_insiders_dock_identity()
                return InstallResult(True, "VS Code Insiders installed successfully.")

            details = (result.stderr or result.stdout).strip()
            return InstallResult(False, "Install failed.", details)
        finally:
            if deb_path:
                try:
                    deb_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def ensure_code_insiders_dock_identity(self) -> InstallResult:
        """Ensure local desktop metadata matches runtime class for GNOME dock grouping."""
        source = Path("/usr/share/applications/code-insiders.desktop")
        if not source.exists():
            return InstallResult(False, "code-insiders desktop file not found.", str(source))

        target_dir = Path.home() / ".local" / "share" / "applications"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "code-insiders.desktop"

        content = source.read_text(encoding="utf-8", errors="replace").splitlines()
        filtered = [
            line
            for line in content
            if not line.startswith("StartupWMClass=")
        ]
        filtered.append("StartupWMClass=Code - Insiders")
        filtered.append("StartupNotify=true")
        target.write_text("\n".join(filtered) + "\n", encoding="utf-8")

        subprocess.run(
            ["update-desktop-database", str(target_dir)],
            capture_output=True,
            text=True,
            check=False,
        )

        return InstallResult(True, "Dock identity metadata updated.", str(target))

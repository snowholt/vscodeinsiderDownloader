"""Install orchestration and dock identity fixes for VS Code Insiders."""

from __future__ import annotations

import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from vsi_updater import __version__
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
USER_AGENT = f"vscode-insiders-updater/{__version__}"
ProgressCallback = Callable[[int, str], None]
CODE_INSIDERS_DESKTOP_OVERRIDES = {
    "StartupWMClass": "Code - Insiders",
    "StartupNotify": "true",
}


class InstallerService:
    """Install service that supports one-time policy bootstrap and no-prompt updates."""

    def _resolve_existing(self, candidates: List[Path]) -> Optional[Path]:
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    def _emit_progress(
        self,
        progress_callback: Optional[ProgressCallback],
        value: int,
        message: str,
    ) -> None:
        if not progress_callback:
            return
        bounded = max(0, min(100, value))
        progress_callback(bounded, message)

    def _apply_desktop_entry_overrides(
        self,
        lines: list[str],
        overrides: dict[str, str],
    ) -> list[str]:
        output: list[str] = []
        override_keys = set(overrides)
        in_desktop_entry = False
        inserted = False

        def append_overrides() -> None:
            for key, value in overrides.items():
                output.append(f"{key}={value}")

        for line in lines:
            stripped = line.strip()
            is_section = stripped.startswith("[") and stripped.endswith("]")
            if is_section:
                if in_desktop_entry and not inserted:
                    append_overrides()
                    inserted = True
                in_desktop_entry = stripped == "[Desktop Entry]"
                output.append(line)
                continue

            if in_desktop_entry and "=" in line:
                key = line.split("=", 1)[0]
                if key in override_keys:
                    continue

            output.append(line)

        if in_desktop_entry and not inserted:
            append_overrides()
            inserted = True

        if not inserted:
            if output and output[-1]:
                output.append("")
            output.append("[Desktop Entry]")
            append_overrides()

        return output

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

    def _download_deb(
        self,
        download_url: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Tuple[Optional[Path], Optional[InstallResult]]:
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".deb")
        tmp_file.close()
        target = Path(tmp_file.name)

        request = urllib.request.Request(download_url, headers={"User-Agent": USER_AGENT})
        try:
            self._emit_progress(progress_callback, 10, "Starting download...")
            with urllib.request.urlopen(request, timeout=30) as response, target.open("wb") as out:
                content_length = response.headers.get("Content-Length")
                total_size = int(content_length) if content_length and content_length.isdigit() else 0

                bytes_read = 0
                milestones = [(1 * 1024 * 1024, 30), (10 * 1024 * 1024, 45), (25 * 1024 * 1024, 60)]
                next_milestone = 0

                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    out.write(chunk)
                    bytes_read += len(chunk)

                    if total_size > 0:
                        ratio = min(1.0, bytes_read / total_size)
                        percent = 10 + int(ratio * 60)
                        self._emit_progress(
                            progress_callback,
                            percent,
                            f"Downloading update... {int(ratio * 100)}%",
                        )
                    elif next_milestone < len(milestones) and bytes_read >= milestones[next_milestone][0]:
                        milestone_percent = milestones[next_milestone][1]
                        self._emit_progress(
                            progress_callback,
                            milestone_percent,
                            "Downloading update...",
                        )
                        next_milestone += 1

            self._emit_progress(progress_callback, 70, "Download complete.")
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
            return None, InstallResult(False, "Download failed.", str(exc))

        return target, None

    def install_update(
        self,
        download_url: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> InstallResult:
        self._emit_progress(progress_callback, 5, "Checking installer prerequisites...")
        helper_script = self._resolve_existing(HELPER_CANDIDATES)
        if not helper_script:
            self._emit_progress(progress_callback, 100, "Install failed.")
            return InstallResult(
                False,
                "System install helper script is missing.",
                "Expected one of: " + ", ".join(str(path) for path in HELPER_CANDIDATES),
            )

        setup_script = self._resolve_existing(SETUP_CANDIDATES)

        if not self.is_passwordless_ready():
            self._emit_progress(progress_callback, 100, "Install failed.")
            return InstallResult(
                False,
                "Passwordless policy is not configured yet.",
                (
                    "Run the one-time setup first: "
                    f"/bin/bash {setup_script}" if setup_script else "Setup script not found."
                ),
            )

        deb_path, error = self._download_deb(download_url, progress_callback=progress_callback)
        if error:
            self._emit_progress(progress_callback, 100, "Download failed.")
            return error

        try:
            self._emit_progress(progress_callback, 80, "Installing package...")
            result = self._run(["sudo", "-n", "/bin/bash", str(helper_script), str(deb_path)])
            if result.returncode == 0:
                self._emit_progress(progress_callback, 92, "Applying desktop integration...")
                self.ensure_code_insiders_dock_identity()
                self._emit_progress(progress_callback, 100, "Update installed successfully.")
                return InstallResult(True, "VS Code Insiders installed successfully.")

            details = (result.stderr or result.stdout).strip()
            self._emit_progress(progress_callback, 100, "Install failed.")
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
        updated = self._apply_desktop_entry_overrides(
            content,
            CODE_INSIDERS_DESKTOP_OVERRIDES,
        )
        target.write_text("\n".join(updated) + "\n", encoding="utf-8")

        subprocess.run(
            ["update-desktop-database", str(target_dir)],
            capture_output=True,
            text=True,
            check=False,
        )

        return InstallResult(True, "Dock identity metadata updated.", str(target))

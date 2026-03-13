"""Version discovery and release notes retrieval for VS Code Insiders."""

from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import List, Optional, Tuple

from vsi_updater import __version__
from vsi_updater.models import UpdateState

UPDATE_API_URL = "https://update.code.visualstudio.com/api/update/linux-deb-x64/insider/latest"
DEFAULT_DOWNLOAD_URL = "https://code.visualstudio.com/sha/download?build=insider&os=linux-deb-x64"
UPDATES_INDEX_URL = "https://code.visualstudio.com/updates/"
USER_AGENT = f"vscode-insiders-updater/{__version__}"


class _ReleaseNotesParser(HTMLParser):
    """Extract a compact summary from the top sections of an updates page."""

    def __init__(self) -> None:
        super().__init__()
        self._in_heading = False
        self._in_paragraph = False
        self._current = []
        self.lines: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag in {"h2", "h3"}:
            self._in_heading = True
            self._current = []
        elif tag == "p":
            self._in_paragraph = True
            self._current = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h2", "h3"} and self._in_heading:
            text = "".join(self._current).strip()
            if text:
                self.lines.append(f"- {text}")
            self._in_heading = False
        elif tag == "p" and self._in_paragraph:
            text = " ".join("".join(self._current).split())
            if text:
                self.lines.append(text)
            self._in_paragraph = False

    def handle_data(self, data: str) -> None:
        if self._in_heading or self._in_paragraph:
            self._current.append(data)


def _http_get(url: str, timeout: int = 15) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _normalize_version(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    value = raw.strip()
    if not value:
        return None
    return value


def _normalize_build(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    value = raw.strip().lower()
    if not value:
        return None
    if re.fullmatch(r"[0-9a-f]{7,64}", value):
        return value
    return None


def _parse_int(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return int(cleaned)
        except ValueError:
            return None
    return None


def _version_tuple(version: Optional[str]) -> Optional[Tuple[int, int, int]]:
    if not version:
        return None
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", version)
    if not match:
        return None
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3) or 0)
    return major, minor, patch


def _is_update_available(
    installed: Optional[str],
    latest: Optional[str],
    installed_build: Optional[str] = None,
    latest_build: Optional[str] = None,
) -> bool:
    if not latest:
        return False
    if not installed:
        return True

    installed_tuple = _version_tuple(installed)
    latest_tuple = _version_tuple(latest)
    if installed_tuple and latest_tuple:
        if latest_tuple != installed_tuple:
            return latest_tuple > installed_tuple

        if latest_build and installed_build:
            # Insider publishes multiple builds under the same product version.
            return latest_build != installed_build

        return False

    if latest_build and installed_build and installed == latest:
        return latest_build != installed_build

    return installed != latest


def _run_cmd(cmd: List[str]) -> Optional[str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return result.stdout.strip()
    except OSError:
        return None
    return None


def _parse_installed_cli_output(output: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not output:
        return None, None

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return None, None

    version = _normalize_version(lines[0])
    build = _normalize_build(lines[1]) if len(lines) > 1 else None
    return version, build


def get_installed_version() -> Tuple[Optional[str], Optional[str]]:
    installed_version: Optional[str] = None
    installed_build: Optional[str] = None

    output = _run_cmd(["code-insiders", "--version"])
    parsed_version, parsed_build = _parse_installed_cli_output(output)
    if parsed_version:
        installed_version = parsed_version
    if parsed_build:
        installed_build = parsed_build

    dpkg_version = _run_cmd(["dpkg-query", "-W", "-f=${Version}", "code-insiders"])
    normalized_dpkg_version = _normalize_version(dpkg_version)
    if not installed_version:
        installed_version = normalized_dpkg_version

    if not installed_build and normalized_dpkg_version:
        match = re.search(r"\+([0-9a-f]{7,64})", normalized_dpkg_version, re.IGNORECASE)
        if match:
            installed_build = _normalize_build(match.group(1))

    return installed_version, installed_build


def _version_to_updates_slug(version: Optional[str]) -> Optional[str]:
    if not version:
        return None
    match = re.search(r"(\d+)\.(\d+)", version)
    if not match:
        return None
    return f"v{match.group(1)}_{match.group(2)}"


def _discover_updates_page_fallback() -> str:
    try:
        html = _http_get(UPDATES_INDEX_URL)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return UPDATES_INDEX_URL

    match = re.search(r"href=\"(/updates/v\d+_\d+)\"", html)
    if not match:
        return UPDATES_INDEX_URL
    return f"https://code.visualstudio.com{match.group(1)}"


def fetch_latest_release_info() -> Tuple[Optional[str], Optional[str], Optional[int], str, str, Optional[str]]:
    """Return latest version/build metadata, download URL, source marker, and check error."""
    try:
        payload = json.loads(_http_get(UPDATE_API_URL))
        latest = _normalize_version(
            payload.get("productVersion")
            or payload.get("name")
            or payload.get("version")
        )
        latest_build = _normalize_build(payload.get("version"))
        latest_timestamp = _parse_int(payload.get("timestamp"))
        url = payload.get("url") or DEFAULT_DOWNLOAD_URL
        return latest, latest_build, latest_timestamp, url, "api", None
    except (json.JSONDecodeError, urllib.error.URLError, ValueError, TimeoutError) as exc:
        return None, None, None, DEFAULT_DOWNLOAD_URL, "api-error", f"{type(exc).__name__}: {exc}"


def resolve_release_notes_url(latest_version: Optional[str]) -> str:
    slug = _version_to_updates_slug(latest_version)
    if slug:
        return f"https://code.visualstudio.com/updates/{slug}"
    return _discover_updates_page_fallback()


def fetch_release_notes_summary(release_notes_url: str) -> str:
    try:
        html = _http_get(release_notes_url)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return "Release notes are currently unavailable."

    parser = _ReleaseNotesParser()
    parser.feed(html)

    cleaned: List[str] = []
    for line in parser.lines:
        if len(cleaned) >= 8:
            break
        if "Try these new features" in line:
            continue
        cleaned.append(line)

    if not cleaned:
        return "Release notes were fetched, but a summary could not be extracted."

    return "\n\n".join(cleaned)


def collect_update_state() -> UpdateState:
    installed_version, installed_build = get_installed_version()
    latest, latest_build, latest_timestamp, download_url, source, check_error = fetch_latest_release_info()
    notes_url = resolve_release_notes_url(latest)
    notes_summary = fetch_release_notes_summary(notes_url)
    check_ok = latest is not None and source == "api"

    return UpdateState(
        installed_version=installed_version,
        installed_build=installed_build,
        latest_version=latest,
        latest_build=latest_build,
        latest_timestamp=latest_timestamp,
        update_available=_is_update_available(installed_version, latest, installed_build, latest_build),
        check_ok=check_ok,
        check_error=check_error,
        release_notes_url=notes_url,
        release_notes_summary=notes_summary,
        download_url=download_url,
        source=source,
    )

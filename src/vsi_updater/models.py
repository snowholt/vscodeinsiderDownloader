"""Shared models for updater state and install results."""

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class UpdateState:
    installed_version: Optional[str]
    installed_build: Optional[str]
    latest_version: Optional[str]
    latest_build: Optional[str]
    latest_timestamp: Optional[int]
    update_available: bool
    check_ok: bool
    check_error: Optional[str]
    release_notes_url: str
    release_notes_summary: str
    download_url: str
    source: str


@dataclass(slots=True)
class InstallResult:
    success: bool
    message: str
    details: str = ""

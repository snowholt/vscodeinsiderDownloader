"""Shared models for updater state and install results."""

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class UpdateState:
    installed_version: Optional[str]
    latest_version: Optional[str]
    update_available: bool
    release_notes_url: str
    release_notes_summary: str
    download_url: str
    source: str


@dataclass(slots=True)
class InstallResult:
    success: bool
    message: str
    details: str = ""

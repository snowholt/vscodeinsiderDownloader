"""CLI fallback for environments without PySide6 or GUI sessions."""

from __future__ import annotations

from vsi_updater.installer_service import InstallerService
from vsi_updater.metadata import APP_AUTHOR, APP_GITHUB, APP_NAME, APP_VERSION
from vsi_updater.update_service import collect_update_state


def print_about() -> None:
    print(f"{APP_NAME} v{APP_VERSION}")
    print(f"Author: {APP_AUTHOR}")
    print(f"GitHub: {APP_GITHUB}")


def check_only() -> int:
    state = collect_update_state()
    print(f"Installed: {state.installed_version or 'not installed'}")
    print(f"Latest: {state.latest_version or 'unavailable'}")
    print(f"Check status: {'ok' if state.check_ok else 'failed'}")
    if state.source:
        print(f"Source: {state.source}")
    if state.check_error:
        print(f"Check error: {state.check_error}")
    print(f"Update available: {'yes' if state.update_available else 'no'}")
    print(f"Release notes: {state.release_notes_url}")
    print("\nSummary:\n")
    print(state.release_notes_summary)
    return 0 if state.check_ok else 1


def interactive_install() -> int:
    state = collect_update_state()
    print(f"Installed: {state.installed_version or 'not installed'}")
    print(f"Latest: {state.latest_version or 'unavailable'}")

    if not state.check_ok:
        print("Unable to verify updates right now.")
        if state.source:
            print(f"Source: {state.source}")
        if state.check_error:
            print(f"Reason: {state.check_error}")
        return 1

    if not state.update_available:
        print("No update available.")
        return 0

    print("\nRelease notes:")
    print(state.release_notes_url)
    print("\nSummary:\n")
    print(state.release_notes_summary)

    answer = input("\nProceed to download and install? [y/N]: ").strip().lower()
    if answer not in {"y", "yes"}:
        print("Cancelled.")
        return 0

    installer = InstallerService()
    if not installer.is_passwordless_ready():
        setup = input("Passwordless policy is not configured. Run one-time setup now? [y/N]: ").strip().lower()
        if setup in {"y", "yes"}:
            setup_result = installer.configure_passwordless_policy()
            print(setup_result.message)
            if setup_result.details:
                print(setup_result.details)
            if not setup_result.success:
                return 1
        else:
            print("Cannot continue without passwordless policy.")
            return 1

    result = installer.install_update(state.download_url)
    print(result.message)
    if result.details:
        print(result.details)
    return 0 if result.success else 1

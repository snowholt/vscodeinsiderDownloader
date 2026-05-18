"""Application entrypoints for GUI and CLI modes."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys

from vsi_updater.cli import check_only, interactive_install, print_about


def _terminal_command() -> list[str] | None:
    candidates = [
        ("x-terminal-emulator", ["-e"]),
        ("gnome-terminal", ["--"]),
        ("kgx", ["--"]),
        ("konsole", ["-e"]),
        ("xfce4-terminal", ["-e"]),
        ("mate-terminal", ["-e"]),
        ("xterm", ["-e"]),
    ]
    for name, args in candidates:
        executable = shutil.which(name)
        if executable:
            return [executable, *args]
    return None


def _run_terminal_fallback(reason: str) -> int:
    if sys.stdin.isatty() or not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        print(reason)
        return interactive_install()

    terminal = _terminal_command()
    if not terminal:
        notifier = shutil.which("notify-send")
        if notifier:
            subprocess.run(
                [notifier, "VS Code Insiders Updater", reason],
                capture_output=True,
                text=True,
                check=False,
            )
        print(reason)
        return 1

    module_command = f"{shlex.quote(sys.executable)} -m vsi_updater.main --no-gui"
    script = (
        f"printf '%s\\n\\n' {shlex.quote(reason)}; "
        f"{module_command}; "
        "status=$?; printf '\\nPress Enter to close...'; read _; exit $status"
    )
    subprocess.Popen([*terminal, "sh", "-lc", script], start_new_session=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VS Code Insiders updater")
    parser.add_argument("--check-only", action="store_true", help="Only check for updates and print summary")
    parser.add_argument("--install", action="store_true", help="Run interactive install flow in terminal")
    parser.add_argument("--no-gui", action="store_true", help="Disable GUI and run terminal mode")
    parser.add_argument("--about", action="store_true", help="Show author and project metadata")
    return parser


def entrypoint() -> int:
    args = build_parser().parse_args()

    if args.about:
        print_about()
        return 0

    if args.check_only:
        return check_only()

    if args.install or args.no_gui:
        return interactive_install()

    try:
        from vsi_updater.ui import run_gui
    except ImportError:
        return _run_terminal_fallback(
            "PySide6 is not available. Falling back to terminal flow."
        )

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(entrypoint())

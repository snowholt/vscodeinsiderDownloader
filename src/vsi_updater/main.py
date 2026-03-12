"""Application entrypoints for GUI and CLI modes."""

from __future__ import annotations

import argparse

from vsi_updater.cli import check_only, interactive_install, print_about


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
        print("PySide6 is not available. Falling back to terminal flow.")
        return interactive_install()

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(entrypoint())

# VS Code Insiders Updater

Production-oriented Linux updater app for VS Code Insiders.

Features included in this implementation:
- Python application architecture with PySide6 GUI.
- Update detection and release notes summary.
- Explicit confirmation prompt before download and install.
- One-time passwordless policy setup for future update installs.
- GNOME dock identity metadata alignment for launcher and VS Code Insiders window class.
- Debian packaging skeleton for publishing the updater app as a .deb package.

## Branding
- App: VS Code Insiders Updater
- Author: Nariman Jafari
- GitHub: https://github.com/snowholt

## Project Layout
- src/vsi_updater/main.py: app entrypoint (GUI + CLI modes)
- src/vsi_updater/ui.py: PySide6 desktop interface
- src/vsi_updater/update_service.py: installed/latest version lookup and release notes retrieval
- src/vsi_updater/installer_service.py: download + install orchestration and dock identity fix
- scripts/system-install-helper.sh: root-only package install helper
- scripts/setup-passwordless-policy.sh: one-time sudoers policy setup
- scripts/install-launcher.sh: local launcher installer for development workflow
- scripts/run-installer-ui.sh: compatibility runner for Python app
- debian/: Debian package metadata and maintainer scripts

## Development Setup
1. Create and activate local virtual environment:
   - python3 -m venv .venv
   - source .venv/bin/activate
2. Install Python dependencies:
   - python -m pip install --upgrade pip
   - python -m pip install -e .
3. Install local launcher:
   - /bin/bash scripts/install-launcher.sh
4. Start app directly:
   - python -m vsi_updater.main

## Update Source
- Primary: VS Code update API for Linux deb insiders build.
- Release notes: https://code.visualstudio.com/updates/ (version page if resolvable, index fallback otherwise).

## Passwordless Mode (One-time Admin Step)
To allow future installs without repeated password prompts, run one-time setup:

- /bin/bash scripts/setup-passwordless-policy.sh

After this, the app uses a scoped helper command through sudo -n for unattended install operations.

## CLI Modes
- Check only:
  - python3 -m vsi_updater.main --check-only
- Terminal install flow:
  - python3 -m vsi_updater.main --no-gui --install
- About info:
  - python3 -m vsi_updater.main --about

## Build Debian Package
1. Install packaging dependencies:
   - sudo apt install -y build-essential devscripts debhelper dh-python pybuild-plugin-pyproject
2. Build:
   - /bin/bash scripts/build-debian-package.sh
3. Resulting .deb files are generated in the parent directory of this project.

## Publish to GitHub
1. Check current git status:
   - git status --short --branch
2. Stage files:
   - git add .
3. Create initial commit:
   - git commit -m "feat: build production VS Code Insiders updater app"
4. Add your GitHub remote:
   - git remote add origin git@github.com:snowholt/vscodeinsiderDownloader.git
5. Push:
   - git push -u origin main

Suggested initial commit message:
- feat: build production VS Code Insiders updater app

Suggested detailed commit body:
- add Python updater app (PySide6 UI + CLI)
- add update detection and release notes summary
- add confirmation-first install flow
- add one-time passwordless policy setup scripts
- add Debian packaging skeleton and build script
- add launcher identity fixes and compatibility wrappers
- add documentation and publish instructions

## Notes on Dock Grouping
- Updater launcher desktop entry sets StartupWMClass=vscode-insiders-updater.
- After install, updater writes a local override for code-insiders desktop metadata with StartupWMClass=Code - Insiders.
- This is targeted first at GNOME Ubuntu Dock behavior.

"""PySide6 GUI for checking and installing VS Code Insiders updates."""

from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vsi_updater.installer_service import InstallerService
from vsi_updater.metadata import (
    APP_AUTHOR,
    APP_DESCRIPTION,
    APP_GITHUB,
    APP_ID,
    APP_NAME,
    APP_REPO,
    APP_VERSION,
)
from vsi_updater.models import UpdateState
from vsi_updater.update_service import collect_update_state


class UpdaterWindow(QWidget):
    """Main updater UI with update status, notes, and install actions."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName(APP_ID)
        self.setWindowTitle(APP_NAME)
        self.resize(760, 540)

        self.installer = InstallerService()
        self.state: Optional[UpdateState] = None

        self.status_label = QLabel("Checking updates...")
        self.installed_label = QLabel("Installed: detecting...")
        self.latest_label = QLabel("Latest: detecting...")
        self.notes_url_label = QLabel("Release notes: pending")
        self.notes_url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.notes = QTextEdit()
        self.notes.setReadOnly(True)

        self.check_button = QPushButton("Check updates")
        self.install_button = QPushButton("Download and install")
        self.setup_button = QPushButton("Setup passwordless mode")
        self.about_button = QPushButton("About")

        self.install_button.setEnabled(False)

        self.check_button.clicked.connect(self.refresh_state)
        self.install_button.clicked.connect(self.install_update)
        self.setup_button.clicked.connect(self.setup_passwordless)
        self.about_button.clicked.connect(self.show_about)

        root = QVBoxLayout()
        root.addWidget(self.status_label)
        root.addWidget(self.installed_label)
        root.addWidget(self.latest_label)
        root.addWidget(self.notes_url_label)
        root.addWidget(self.notes)

        buttons = QHBoxLayout()
        buttons.addWidget(self.check_button)
        buttons.addWidget(self.setup_button)
        buttons.addWidget(self.install_button)
        buttons.addWidget(self.about_button)
        root.addLayout(buttons)

        self.setLayout(root)
        self.refresh_state()

    def refresh_state(self) -> None:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.state = collect_update_state()
        finally:
            QApplication.restoreOverrideCursor()

        installed = self.state.installed_version or "not installed"
        latest = self.state.latest_version or "unavailable"

        self.installed_label.setText(f"Installed: {installed}")
        self.latest_label.setText(f"Latest: {latest}")
        self.notes_url_label.setText(f"Release notes: {self.state.release_notes_url}")
        self.notes.setPlainText(self.state.release_notes_summary)

        if not self.state.check_ok:
            self.status_label.setText("Unable to verify updates right now.")
            self.install_button.setEnabled(False)
        elif self.state.update_available:
            self.status_label.setText("Update available.")
            self.install_button.setEnabled(True)
        else:
            self.status_label.setText("You are up to date.")
            self.install_button.setEnabled(False)

    def setup_passwordless(self) -> None:
        result = self.installer.configure_passwordless_policy()
        if result.success:
            QMessageBox.information(self, APP_NAME, result.message)
            return

        msg = result.message
        if result.details:
            msg = f"{msg}\n\nDetails:\n{result.details}"
        QMessageBox.warning(self, APP_NAME, msg)

    def install_update(self) -> None:
        if not self.state:
            QMessageBox.warning(self, APP_NAME, "No update state available. Check updates first.")
            return

        if not self.state.update_available:
            QMessageBox.information(self, APP_NAME, "No update is available right now.")
            return

        if not self.installer.is_passwordless_ready():
            answer = QMessageBox.question(
                self,
                APP_NAME,
                (
                    "Passwordless mode is not configured.\n\n"
                    "Do you want to run one-time setup now?"
                ),
            )
            if answer != QMessageBox.Yes:
                return
            setup_result = self.installer.configure_passwordless_policy()
            if not setup_result.success:
                details = f"\n\nDetails:\n{setup_result.details}" if setup_result.details else ""
                QMessageBox.warning(self, APP_NAME, setup_result.message + details)
                return

        confirm = QMessageBox.question(
            self,
            APP_NAME,
            (
                "An update is available.\n\n"
                f"Installed: {self.state.installed_version or 'none'}\n"
                f"Latest: {self.state.latest_version or 'unknown'}\n\n"
                "Proceed to download and install?"
            ),
        )
        if confirm != QMessageBox.Yes:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = self.installer.install_update(self.state.download_url)
        finally:
            QApplication.restoreOverrideCursor()

        if result.success:
            QMessageBox.information(self, APP_NAME, result.message)
            self.refresh_state()
            return

        details = f"\n\nDetails:\n{result.details}" if result.details else ""
        QMessageBox.critical(self, APP_NAME, result.message + details)

    def show_about(self) -> None:
        QMessageBox.information(
            self,
            f"About {APP_NAME}",
            (
                f"{APP_NAME}\n"
                f"Version: {APP_VERSION}\n"
                f"Description: {APP_DESCRIPTION}\n"
                f"Author: {APP_AUTHOR}\n"
                f"GitHub: {APP_GITHUB}\n"
                f"Repository owner: {APP_REPO}"
            ),
        )


def run_gui() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName(APP_ID)

    window = UpdaterWindow()
    window.show()
    return app.exec()

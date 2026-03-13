"""PySide6 GUI for checking and installing VS Code Insiders updates."""

from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
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
from vsi_updater.models import InstallResult, UpdateState
from vsi_updater.update_service import collect_update_state


def _short_commit(value: Optional[str]) -> str:
    if not value:
        return "unavailable"
    return value[:12]


class _InstallWorker(QObject):
    """Run install workflow away from the UI thread to keep the app responsive."""

    finished = Signal(object)
    progress = Signal(int, str)

    def __init__(self, installer: InstallerService, download_url: str) -> None:
        super().__init__()
        self._installer = installer
        self._download_url = download_url

    @Slot()
    def run(self) -> None:
        result = self._installer.install_update(
            self._download_url,
            progress_callback=self._emit_progress,
        )
        self.finished.emit(result)

    def _emit_progress(self, value: int, message: str) -> None:
        self.progress.emit(value, message)


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
        self.installed_commit_label = QLabel("Installed commit: detecting...")
        self.latest_label = QLabel("Latest: detecting...")
        self.latest_commit_label = QLabel("Latest commit: detecting...")
        self.notes_url_label = QLabel("Release notes: pending")
        self.notes_url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.notes = QTextEdit()
        self.notes.setReadOnly(True)

        self.check_button = QPushButton("Check updates")
        self.install_button = QPushButton("Download and install")
        self.setup_button = QPushButton("Setup passwordless mode")
        self.about_button = QPushButton("About")
        self._install_thread: Optional[QThread] = None
        self._install_worker: Optional[_InstallWorker] = None
        self._progress_dialog: Optional[QProgressDialog] = None

        self.install_button.setEnabled(False)

        self.check_button.clicked.connect(self.refresh_state)
        self.install_button.clicked.connect(self.install_update)
        self.setup_button.clicked.connect(self.setup_passwordless)
        self.about_button.clicked.connect(self.show_about)

        root = QVBoxLayout()
        root.addWidget(self.status_label)
        root.addWidget(self.installed_label)
        root.addWidget(self.installed_commit_label)
        root.addWidget(self.latest_label)
        root.addWidget(self.latest_commit_label)
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
        installed_commit = _short_commit(self.state.installed_build)
        latest = self.state.latest_version or "unavailable"
        latest_commit = _short_commit(self.state.latest_build)

        self.installed_label.setText(f"Installed: {installed}")
        self.installed_commit_label.setText(f"Installed commit: {installed_commit}")
        self.latest_label.setText(f"Latest: {latest}")
        self.latest_commit_label.setText(f"Latest commit: {latest_commit}")
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

        if self._install_thread and self._install_thread.isRunning():
            QMessageBox.information(self, APP_NAME, "An update installation is already running.")
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
                f"Installed commit: {_short_commit(self.state.installed_build)}\n"
                f"Latest: {self.state.latest_version or 'unknown'}\n\n"
                f"Latest commit: {_short_commit(self.state.latest_build)}\n\n"
                "Proceed to download and install?"
            ),
        )
        if confirm != QMessageBox.Yes:
            return

        self._start_install(self.state.download_url)

    def _start_install(self, download_url: str) -> None:
        self.status_label.setText("Downloading and installing update. Please wait...")
        self.check_button.setEnabled(False)
        self.setup_button.setEnabled(False)
        self.install_button.setEnabled(False)

        self._install_thread = QThread(self)
        self._install_worker = _InstallWorker(self.installer, download_url)
        self._install_worker.moveToThread(self._install_thread)

        self._install_thread.started.connect(self._install_worker.run)
        self._install_worker.progress.connect(self._on_install_progress)
        self._install_worker.finished.connect(self._on_install_finished)
        self._install_worker.finished.connect(self._install_thread.quit)
        self._install_thread.finished.connect(self._cleanup_install_thread)

        self._progress_dialog = QProgressDialog("Preparing update...", "", 0, 100, self)
        self._progress_dialog.setWindowTitle(APP_NAME)
        self._progress_dialog.setCancelButton(None)
        self._progress_dialog.setAutoClose(False)
        self._progress_dialog.setAutoReset(False)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setWindowModality(Qt.ApplicationModal)
        self._progress_dialog.setValue(0)
        self._progress_dialog.show()

        self._install_thread.start()

    @Slot(int, str)
    def _on_install_progress(self, value: int, message: str) -> None:
        self.status_label.setText(message)
        if self._progress_dialog:
            self._progress_dialog.setLabelText(message)
            self._progress_dialog.setValue(max(0, min(100, value)))

    @Slot(object)
    def _on_install_finished(self, result: InstallResult) -> None:
        self.check_button.setEnabled(True)
        self.setup_button.setEnabled(True)
        if result.success:
            QMessageBox.information(self, APP_NAME, result.message)
            self.refresh_state()
            return

        details = f"\n\nDetails:\n{result.details}" if result.details else ""
        QMessageBox.critical(self, APP_NAME, result.message + details)

    @Slot()
    def _cleanup_install_thread(self) -> None:
        if self._progress_dialog:
            self._progress_dialog.setValue(100)
            self._progress_dialog.close()
            self._progress_dialog.deleteLater()
        self._progress_dialog = None
        if self._install_worker:
            self._install_worker.deleteLater()
        self._install_worker = None
        self._install_thread = None
        if self.state and self.state.check_ok and self.state.update_available:
            self.install_button.setEnabled(True)

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

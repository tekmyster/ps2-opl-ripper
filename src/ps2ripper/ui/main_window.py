from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ps2ripper import __version__
from ps2ripper.core.cancellation import CancellationToken
from ps2ripper.core.exceptions import ValidationError
from ps2ripper.core.logging import serial_for_log
from ps2ripper.core.models import DiscIdentity, MediaType, PhysicalDisk, ProgressSnapshot, TrackKind
from ps2ripper.core.workflow import InstallResult, rip_and_install
from ps2ripper.opl.layout import OPLDrive
from ps2ripper.ui.dialogs import (
    AboutDialog,
    AdvancedSettingsDialog,
    EraseConfirmationDialog,
    LicensesDialog,
    rip_settings,
)
from ps2ripper.ui.workers import TaskWorker
from ps2ripper.windows.device_enumeration import validate_opl_compatibility
from ps2ripper.windows.native import human_size
from ps2ripper.windows.optical_api import NativeOpticalDevice, enumerate_optical_drives
from ps2ripper.windows.storage_api import PhysicalDiskManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, log_path: Path) -> None:
        super().__init__()
        self.log_path = log_path
        self.settings = QSettings("PS2Ripper", "PS2Ripper")
        self.thread_pool = QThreadPool.globalInstance()
        self.disk_manager = PhysicalDiskManager()
        self.disks: tuple[PhysicalDisk, ...] = ()
        self.optical_drives = ()
        self.preferred_optical_instance_id: str | None = None
        self.selected_disk: PhysicalDisk | None = None
        self.opl_root: Path | None = None
        self.disc: DiscIdentity | None = None
        self.current_token: CancellationToken | None = None
        self.busy = False
        self.setWindowTitle(f"PS2 OPL Ripper {__version__}")
        self.setMinimumSize(780, 650)
        self._build_ui()
        QTimer.singleShot(0, self._welcome)

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)

        destination_group = QGroupBox("1. Select PS2 USB drive")
        destination_layout = QVBoxLayout(destination_group)
        row = QHBoxLayout()
        self.disk_combo = QComboBox()
        self.disk_combo.currentIndexChanged.connect(self._show_disk)
        self.refresh_disks_button = QPushButton("Refresh")
        self.refresh_disks_button.clicked.connect(self.refresh_disks)
        row.addWidget(self.disk_combo, 1)
        row.addWidget(self.refresh_disks_button)
        destination_layout.addLayout(row)
        self.ready_drive_banner = QLabel("<b>PS2 READY DRIVE DETECTED</b>")
        self.ready_drive_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ready_drive_banner.setStyleSheet(
            "QLabel { color: #146c2e; background: #e7f5eb; border: 1px solid #6fa77c; "
            "padding: 7px; }"
        )
        self.ready_drive_banner.setVisible(False)
        destination_layout.addWidget(self.ready_drive_banner)
        self.reformat_checkbox = QCheckBox(
            "Reformat selected drive before use (ERASES ALL DATA)"
        )
        self.reformat_checkbox.setAccessibleName("Reformat selected USB drive")
        self.reformat_checkbox.setStyleSheet(
            "QCheckBox:checked { color: #a40000; font-weight: bold; }"
        )
        self.reformat_checkbox.setChecked(False)
        self.reformat_checkbox.setEnabled(False)
        self.reformat_checkbox.toggled.connect(self._update_drive_action)
        destination_layout.addWidget(self.reformat_checkbox)
        self.disk_details = QLabel("No USB storage devices inspected yet.")
        self.disk_details.setWordWrap(True)
        self.disk_details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        destination_layout.addWidget(self.disk_details)
        self.prepare_button = QPushButton("Validate selected drive")
        self.prepare_button.clicked.connect(self.prepare_selected_disk)
        self.prepare_button.setEnabled(False)
        destination_layout.addWidget(self.prepare_button)
        outer.addWidget(destination_group)

        optical_group = QGroupBox("2. Insert PS2 disc")
        optical_layout = QVBoxLayout(optical_group)
        optical_row = QHBoxLayout()
        self.optical_combo = QComboBox()
        self.refresh_optical_button = QPushButton("Refresh drives")
        self.refresh_optical_button.clicked.connect(self.refresh_optical)
        self.scan_disc_button = QPushButton("Read disc")
        self.scan_disc_button.clicked.connect(self.scan_disc)
        self.eject_button = QPushButton("Eject disc")
        self.eject_button.clicked.connect(self.eject_disc)
        optical_row.addWidget(self.optical_combo, 1)
        optical_row.addWidget(self.refresh_optical_button)
        optical_row.addWidget(self.scan_disc_button)
        optical_row.addWidget(self.eject_button)
        optical_layout.addLayout(optical_row)
        self.disc_details = QLabel("Select and prepare a destination drive first.")
        self.disc_details.setWordWrap(True)
        optical_layout.addWidget(self.disc_details)
        outer.addWidget(optical_group)

        rip_group = QGroupBox("3. Rip, verify, and install")
        rip_layout = QFormLayout(rip_group)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Enter the game title (offline; never guessed)")
        self.title_edit.textChanged.connect(self._update_rip_enabled)
        rip_layout.addRow("Game title", self.title_edit)
        self.rip_button = QPushButton("Rip Game")
        self.rip_button.clicked.connect(self.start_rip)
        self.rip_button.setEnabled(False)
        rip_layout.addRow("", self.rip_button)
        outer.addWidget(rip_group)

        progress_group = QGroupBox("Operation progress")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        progress_buttons = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_operation)
        self.cancel_button.setEnabled(False)
        self.next_button = QPushButton("Rip Next Game")
        self.next_button.clicked.connect(self.rip_next)
        self.next_button.setVisible(False)
        self.exit_button = QPushButton("Exit")
        self.exit_button.clicked.connect(self.close)
        progress_buttons.addWidget(self.cancel_button)
        progress_buttons.addStretch(1)
        progress_buttons.addWidget(self.next_button)
        progress_buttons.addWidget(self.exit_button)
        progress_layout.addLayout(progress_buttons)
        outer.addWidget(progress_group)

        self.setCentralWidget(central)
        advanced = QAction("Advanced settings…", self)
        advanced.triggered.connect(lambda: AdvancedSettingsDialog(self.settings, self).exec())
        self.menuBar().addMenu("Settings").addAction(advanced)
        help_menu = self.menuBar().addMenu("Help")
        licenses = QAction("Licenses and third-party notices…", self)
        licenses.triggered.connect(lambda: LicensesDialog(self).exec())
        about = QAction("About PS2 OPL Ripper…", self)
        about.triggered.connect(lambda: AboutDialog(self).exec())
        help_menu.addAction(licenses)
        help_menu.addSeparator()
        help_menu.addAction(about)
        self.statusBar().showMessage(f"Log: {self.log_path}")
        self._set_optical_enabled(False)

    def _welcome(self) -> None:
        QMessageBox.information(
            self,
            "Welcome to PS2 OPL Ripper",
            "This program prepares a USB drive for Open PS2 Loader and creates backup images "
            "of PlayStation 2 discs you own.\n\nExisting PS2-ready drives are detected and reused "
            "without formatting. Reformat is never selected automatically and always requires "
            "the full typed confirmation.",
        )
        self.refresh_disks()

    def _run_task(self, function, *args, on_result=None, **kwargs) -> None:
        if self.busy:
            return
        self.busy = True
        self.cancel_button.setEnabled(self.current_token is not None)
        self._refresh_controls()
        worker = TaskWorker(function, *args, **kwargs)
        worker.signals.progress.connect(self._progress)
        worker.signals.error.connect(self._task_error)
        if on_result:
            worker.signals.result.connect(on_result)
        worker.signals.finished.connect(self._task_finished)
        self.thread_pool.start(worker)

    def _task_finished(self) -> None:
        self.busy = False
        self.current_token = None
        self.cancel_button.setEnabled(False)
        self._refresh_controls()

    def _task_error(self, exc: BaseException, details: str) -> None:
        self.progress_label.setText(str(exc))
        QMessageBox.critical(self, "Operation failed", str(exc))

    def _refresh_controls(self) -> None:
        self.refresh_disks_button.setEnabled(not self.busy)
        self._update_drive_action()
        self.refresh_optical_button.setEnabled(not self.busy and self.opl_root is not None)
        self.scan_disc_button.setEnabled(
            not self.busy and self.opl_root is not None and self.optical_combo.currentIndex() >= 0
        )
        self.eject_button.setEnabled(not self.busy and self.optical_combo.currentIndex() >= 0)
        self._update_rip_enabled()

    def _set_optical_enabled(self, enabled: bool) -> None:
        self.optical_combo.setEnabled(enabled)
        self.refresh_optical_button.setEnabled(enabled)
        self.scan_disc_button.setEnabled(enabled)
        self.eject_button.setEnabled(enabled)

    @staticmethod
    def _enumerate_disks_task(*, progress=None):
        return PhysicalDiskManager().enumerate_usb_disks()

    def refresh_disks(self) -> None:
        self.opl_root = None
        self.selected_disk = None
        self.disc = None
        self.ready_drive_banner.setVisible(False)
        self.reformat_checkbox.setChecked(False)
        self.reformat_checkbox.setEnabled(False)
        self.disk_combo.clear()
        self.disk_details.setText("Inspecting USB storage devices…")
        self._set_optical_enabled(False)
        self._run_task(self._enumerate_disks_task, on_result=self._disks_ready)

    def _disks_ready(self, disks: tuple[PhysicalDisk, ...]) -> None:
        self.disks = disks
        for disk in disks:
            logger.info(
                "Detected %s model=%s manufacturer=%s serial=%s bus=%s capacity=%d style=%s volumes=%s safety=%s",
                disk.physical_name,
                disk.model,
                disk.manufacturer,
                serial_for_log(disk.serial),
                disk.bus_type,
                disk.capacity,
                disk.partition_style.name,
                [point for volume in disk.volumes for point in volume.mount_points],
                list(disk.safety_reasons),
            )
        self.disk_combo.blockSignals(True)
        self.disk_combo.clear()
        for disk in disks:
            mounts = (
                ", ".join(point for volume in disk.volumes for point in volume.mount_points)
                or "No drive letter"
            )
            compatible, _reasons = validate_opl_compatibility(disk)
            prefix = "PS2 Ready — " if compatible else ""
            self.disk_combo.addItem(
                f"{prefix}{disk.physical_name} — {disk.manufacturer} {disk.model} — "
                f"{human_size(disk.capacity)} — {mounts}"
            )
        self.disk_combo.blockSignals(False)
        if not disks:
            self.disk_details.setText(
                "No USB HDD/SSD was detected. Connect one and select Refresh."
            )
        self._show_disk()

    def _show_disk(self) -> None:
        index = self.disk_combo.currentIndex()
        if index < 0 or index >= len(self.disks):
            self.ready_drive_banner.setVisible(False)
            self.reformat_checkbox.setChecked(False)
            self.reformat_checkbox.setEnabled(False)
            self.prepare_button.setEnabled(False)
            return
        disk = self.disks[index]
        previous_disk = self.selected_disk
        if previous_disk is not None and (
            previous_disk.number != disk.number
            or previous_disk.identity_tuple() != disk.identity_tuple()
        ):
            self.opl_root = None
            self.disc = None
            self._set_optical_enabled(False)
            self.disc_details.setText("Select and prepare this destination drive first.")
        self.selected_disk = disk
        compatible, reasons = validate_opl_compatibility(disk)
        self.ready_drive_banner.setVisible(compatible)
        self.reformat_checkbox.setChecked(False)
        self.reformat_checkbox.setEnabled(disk.destructive_access_allowed)
        if disk.safety_reasons:
            self.reformat_checkbox.setToolTip(
                "Reformatting is blocked because this physical device has a protected role."
            )
        else:
            self.reformat_checkbox.setToolTip(
                "Optional. Leave unchecked to preserve every existing game and file."
            )
        volumes = (
            "; ".join(
                f"{', '.join(volume.mount_points) or volume.guid_path} — {volume.filesystem or 'Unknown'}"
                for volume in disk.volumes
            )
            or "No mounted volumes"
        )
        safety = (
            "<br>Destructive access blocked:<br>• " + "<br>• ".join(disk.safety_reasons)
            if disk.safety_reasons
            else ""
        )
        self.disk_details.setText(
            f"<b>{disk.physical_name}</b><br>Model: {disk.manufacturer} {disk.model}<br>"
            f"Serial: {disk.serial or 'Unavailable'}<br>Capacity: {human_size(disk.capacity)} "
            f"({disk.capacity:,} bytes)<br>Bus: {disk.bus_type}<br>Device class: "
            f"{'Removable' if disk.removable else 'Fixed'}<br>Partition table: "
            f"{disk.partition_style.name}<br>Volumes: {volumes}"
            + (
                "<br>Status: <b>Ready for OPL; existing games and folders will be preserved.</b>"
                if compatible
                else "<br>OPL compatibility: " + " ".join(reasons)
            )
            + safety
        )
        self._update_drive_action()

    def _update_drive_action(self) -> None:
        index = self.disk_combo.currentIndex()
        if index < 0 or index >= len(self.disks):
            self.prepare_button.setText("Validate selected drive")
            self.prepare_button.setEnabled(False)
            return
        disk = self.disks[index]
        compatible, _reasons = validate_opl_compatibility(disk)
        reformat = self.reformat_checkbox.isChecked()
        self.reformat_checkbox.setEnabled(not self.busy and disk.destructive_access_allowed)
        if compatible and not reformat:
            text = "Use Existing PS2 Drive"
        elif reformat:
            text = "Reformat Selected Drive" if compatible else "Initialize Drive for OPL"
        else:
            text = "Review Drive Requirements"
        self.prepare_button.setText(text)
        self.prepare_button.setEnabled(not self.busy)

    def prepare_selected_disk(self) -> None:
        if not self.selected_disk:
            return
        disk = self.selected_disk
        compatible, reasons = validate_opl_compatibility(disk)
        reformat_requested = self.reformat_checkbox.isChecked()
        if compatible and not reformat_requested:
            mount = next((point for volume in disk.volumes for point in volume.mount_points), None)
            if not mount:
                QMessageBox.critical(
                    self, "Drive inaccessible", "The compatible exFAT volume has no mount point."
                )
                return
            root = Path(mount)
            try:
                OPLDrive(root).create_directories()
            except BaseException as exc:
                QMessageBox.critical(self, "Unable to prepare OPL folders", str(exc))
                return
            self.opl_root = root
            logger.info(
                "Selected %s model=%s serial=%s capacity=%d",
                disk.physical_name,
                disk.model,
                serial_for_log(disk.serial),
                disk.capacity,
            )
            self.progress_label.setText(
                "Existing PS2-ready drive selected. No formatting was performed; existing "
                "games and files were preserved."
            )
            self.refresh_optical()
            return
        reason_text = "\n".join(f"• {reason}" for reason in reasons)
        if not reformat_requested:
            QMessageBox.information(
                self,
                "Drive is not OPL-compatible",
                f"{reason_text}\n\nThe drive has not been changed. To initialize it as MBR/exFAT, "
                "select 'Reformat selected drive before use' and review the destructive "
                "confirmation details.",
            )
            return
        if disk.safety_reasons:
            QMessageBox.critical(
                self,
                "Initialization blocked",
                (f"The drive is incompatible:\n{reason_text}\n\n" if reasons else "")
                + "Destructive access is blocked:\n"
                + "\n".join(f"• {reason}" for reason in disk.safety_reasons),
            )
            return
        response = QMessageBox.warning(
            self,
            "Confirm drive reformat",
            (
                "This drive is already PS2-ready, but reformatting was explicitly selected."
                if compatible
                else f"The drive is incompatible:\n{reason_text}"
            )
            + "\n\nReformat this physical drive as one MBR/exFAT partition? "
            "All existing games, partitions, and files will be erased.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if response != QMessageBox.Yes:
            return
        dialog = EraseConfirmationDialog(disk, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self.current_token = CancellationToken()
        self.progress_label.setText("Locking volumes and re-verifying physical disk identity…")

        def format_task(*, progress=None):
            result = self.disk_manager.initialize_mbr_exfat(
                disk, dialog.confirmation.text(), self.current_token
            )
            remounted = self.disk_manager.wait_for_remount(
                disk, self.current_token, honor_cancellation=False
            )
            return result, remounted

        self._run_task(format_task, on_result=self._format_complete)

    def _format_complete(self, result) -> None:
        _format_result, disk = result
        self.disks = tuple(disk if item.number == disk.number else item for item in self.disks)
        self.selected_disk = disk
        compatible, reasons = validate_opl_compatibility(disk)
        if not compatible:
            self._task_error(
                ValidationError("Post-format verification failed: " + " ".join(reasons)), ""
            )
            return
        mount = next((point for volume in disk.volumes for point in volume.mount_points), None)
        if not mount:
            self._task_error(
                ValidationError("The new exFAT volume did not receive a mount point."), ""
            )
            return
        self.opl_root = Path(mount)
        OPLDrive(self.opl_root).create_directories()
        self.reformat_checkbox.setChecked(False)
        self.ready_drive_banner.setVisible(True)
        self.progress_label.setText(
            "USB drive initialized and verified as MBR / exFAT / OPL ready."
        )
        QTimer.singleShot(100, self.refresh_optical)

    @staticmethod
    def _enumerate_optical_task(*, progress=None):
        return enumerate_optical_drives()

    def refresh_optical(self) -> None:
        if not self.opl_root:
            return
        current_index = self.optical_combo.currentIndex()
        if 0 <= current_index < len(self.optical_drives):
            self.preferred_optical_instance_id = self.optical_drives[current_index].instance_id
        self.optical_combo.clear()
        self.disc_details.setText("Detecting optical drives…")
        self._run_task(self._enumerate_optical_task, on_result=self._optical_ready)

    def _optical_ready(self, drives) -> None:
        self.optical_drives = drives
        for drive in drives:
            logger.info(
                "Detected optical drive path=%s letter=%s model=%s %s revision=%s",
                drive.device_path,
                drive.drive_letter,
                drive.vendor,
                drive.product,
                drive.revision,
            )
        self.optical_combo.clear()
        for drive in drives:
            self.optical_combo.addItem(drive.display_name)
        preferred_index = next(
            (
                index
                for index, drive in enumerate(drives)
                if drive.instance_id == self.preferred_optical_instance_id
            ),
            0,
        )
        if drives:
            self.optical_combo.setCurrentIndex(preferred_index)
        if drives:
            self.disc_details.setText("Insert a PlayStation 2 game disc, then select Read disc.")
        else:
            self.disc_details.setText(
                "No optical drive was detected. Connect one and select Refresh drives."
            )
        self._set_optical_enabled(bool(drives))

    def scan_disc(self) -> None:
        index = self.optical_combo.currentIndex()
        if index < 0:
            return
        drive = self.optical_drives[index]
        self.disc_details.setText("Reading media information and PS2 SYSTEM.CNF…")

        def inspect_task(*, progress=None):
            from ps2ripper.optical.media_detector import inspect_disc

            with NativeOpticalDevice(drive) as device:
                return inspect_disc(device)

        self._run_task(inspect_task, on_result=self._disc_ready)

    def _disc_ready(self, disc: DiscIdentity) -> None:
        self.disc = disc if disc.game_id else None
        logger.info(
            "Media inspected type=%s game_id=%s sectors=%d sector_size=%d tracks=%s",
            disc.media_type.name,
            disc.game_id or "unrecognized",
            disc.total_sectors,
            disc.sector_size,
            [
                (track.number, track.kind.value, track.start_lba, track.end_lba)
                for track in disc.tracks
            ],
        )
        if disc.media_type is MediaType.NO_MEDIA:
            self.disc_details.setText("Insert a PlayStation 2 game disc. Waiting…")
        elif not disc.game_id:
            self.disc_details.setText(
                f"Unsupported media: {disc.media_type.name.replace('_', ' ').title()}. "
                "No recognizable PS2 SYSTEM.CNF was found."
            )
        else:
            mixed = any(track.kind is TrackKind.AUDIO for track in disc.tracks)
            self.disc_details.setText(
                f"<b>Game ID: {disc.game_id}</b><br>Disc type: {disc.media_type.name.replace('_', ' ')}"
                f"<br>Sectors: {disc.total_sectors:,}"
                + ("<br><b>Mixed-mode CD: audio tracks detected.</b>" if mixed else "")
            )
            self.title_edit.setFocus()
        self._update_rip_enabled()

    def _update_rip_enabled(self) -> None:
        self.rip_button.setEnabled(
            not self.busy
            and self.opl_root is not None
            and self.disc is not None
            and bool(self.title_edit.text().strip())
        )

    def start_rip(self) -> None:
        if not self.disc or not self.opl_root:
            return
        title = self.title_edit.text().strip()
        try:
            destination = OPLDrive(self.opl_root).destination_for_game(
                self.disc.media_type, self.disc.game_id, title
            )
        except BaseException as exc:
            QMessageBox.warning(self, "Invalid title", str(exc))
            return
        replace = False
        if destination.exists():
            box = QMessageBox(self)
            box.setWindowTitle("Game already exists")
            box.setText(f"{destination.name} already exists.")
            skip = box.addButton("Skip", QMessageBox.RejectRole)
            replace_button = box.addButton("Replace…", QMessageBox.DestructiveRole)
            alternate = box.addButton("Save with alternate title", QMessageBox.ActionRole)
            cancel = box.addButton(QMessageBox.Cancel)
            box.exec()
            clicked = box.clickedButton()
            if clicked in (skip, cancel):
                return
            if clicked is alternate:
                alternate_title, ok = QInputDialog.getText(
                    self, "Alternate title", "Game title", text=title
                )
                if not ok:
                    return
                self.title_edit.setText(alternate_title)
                self.start_rip()
                return
            if clicked is replace_button:
                response = QMessageBox.warning(
                    self,
                    "Confirm replacement",
                    f"Replace the existing verified game file?\n{destination}",
                    QMessageBox.Yes | QMessageBox.Cancel,
                    QMessageBox.Cancel,
                )
                if response != QMessageBox.Yes:
                    return
                replace = True
        archive_only = False
        force_archive = False
        if self.disc.media_type is MediaType.PS2_CD and any(
            track.kind is TrackKind.AUDIO for track in self.disc.tracks
        ):
            box = QMessageBox(self)
            box.setWindowTitle("Mixed-mode PS2 CD detected")
            box.setText(
                "This disc contains audio tracks that cannot be represented completely by a single "
                "standard OPL ISO. No audio will be silently discarded."
            )
            both = box.addButton("Create archival BIN/CUE and OPL data ISO", QMessageBox.AcceptRole)
            archive = box.addButton("Create archival BIN/CUE only", QMessageBox.ActionRole)
            cancel = box.addButton(QMessageBox.Cancel)
            box.exec()
            if box.clickedButton() is cancel:
                return
            archive_only = box.clickedButton() is archive
            force_archive = box.clickedButton() in (both, archive)
        drive = self.optical_drives[self.optical_combo.currentIndex()]
        self.current_token = CancellationToken()
        self.next_button.setVisible(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting rip…")
        self._run_task(
            rip_and_install,
            drive,
            self.disc,
            title,
            self.opl_root,
            rip_settings(self.settings),
            self.current_token,
            replace_existing=replace,
            archive_only=archive_only,
            force_retain_archive=force_archive,
            on_result=self._rip_complete,
        )

    def _progress(self, snapshot: ProgressSnapshot) -> None:
        fraction = snapshot.fraction
        self.progress_bar.setValue(max(0, min(1000, int(fraction * 1000))))
        speed = (
            human_size(int(snapshot.current_bytes_per_second)) + "/s"
            if snapshot.current_bytes_per_second
            else "—"
        )
        average = (
            human_size(int(snapshot.average_bytes_per_second)) + "/s"
            if snapshot.average_bytes_per_second
            else "—"
        )
        lba = f" — LBA {snapshot.current_lba:,}" if snapshot.current_lba is not None else ""
        self.progress_label.setText(
            f"{snapshot.operation}: {human_size(snapshot.completed_bytes)} / {human_size(snapshot.total_bytes)} "
            f"({fraction * 100:.1f}%){lba} — current {speed} — average {average} — "
            f"elapsed {snapshot.elapsed_seconds:.1f}s — retries {snapshot.retries}"
        )

    def _rip_complete(self, result: InstallResult) -> None:
        self.progress_bar.setValue(1000)
        if result.destination:
            self.progress_label.setText(
                f"Game copied and verified. {result.destination} — SHA-256 {result.destination_sha256}"
            )
            QMessageBox.information(
                self,
                "Game successfully installed and verified",
                f"{result.destination}\n\nSHA-256:\n{result.destination_sha256}",
            )
        else:
            self.progress_label.setText(f"Archival BIN/CUE created at {result.archive_bin}")
            QMessageBox.information(
                self,
                "CD archive complete",
                f"BIN: {result.archive_bin}\nCUE: {result.archive_cue}\nSHA-256: {result.source_sha256}",
            )
        self.next_button.setVisible(True)
        if self.settings.value("rip/autoEject", False, bool):
            self.eject_disc()

    def cancel_operation(self) -> None:
        if self.current_token:
            self.current_token.request()
            self.progress_label.setText(
                "Cancel requested — finishing the current critical operation safely…"
                if self.current_token.in_critical_section
                else "Cancel requested…"
            )
            self.cancel_button.setEnabled(False)

    def eject_disc(self) -> None:
        index = self.optical_combo.currentIndex()
        if index < 0:
            return
        drive = self.optical_drives[index]
        try:
            with NativeOpticalDevice(drive) as device:
                device.eject()
        except BaseException as exc:
            QMessageBox.warning(self, "Unable to eject disc", str(exc))

    def rip_next(self) -> None:
        self.disc = None
        self.title_edit.clear()
        self.next_button.setVisible(False)
        self.progress_bar.setValue(0)
        self.disc_details.setText("Insert the next PlayStation 2 game disc, then select Read disc.")
        self._update_rip_enabled()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.busy:
            QMessageBox.warning(
                self,
                "Operation in progress",
                "Cancel or finish the current operation before exiting.",
            )
            event.ignore()
            return
        event.accept()

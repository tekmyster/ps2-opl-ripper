from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
)

from ps2ripper import __version__
from ps2ripper.core.models import PhysicalDisk
from ps2ripper.core.workflow import RipSettings
from ps2ripper.licensing import LicenseDocument, load_license_documents, third_party_overview
from ps2ripper.windows.native import human_size
from ps2ripper.windows.storage_api import expected_erase_confirmation


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About PS2 OPL Ripper")
        self.setMinimumWidth(600)
        layout = QVBoxLayout(self)
        heading = QLabel(f"<h2>PS2 OPL Ripper {__version__}</h2>")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)
        description = QTextBrowser()
        description.setOpenExternalLinks(True)
        description.setMaximumHeight(250)
        description.setHtml(
            "<p>A self-contained Windows application that prepares an MBR/exFAT USB drive "
            "for Open PS2 Loader and creates verified backup images of PlayStation 2 discs.</p>"
            "<p><b>Use this program only to back up discs you own.</b></p>"
            "<p>PS2 OPL Ripper is free software licensed under the GNU General Public License "
            "version 3 or later and is provided without warranty.</p>"
            "<p>The executable includes CPython, Qt for Python, FATtools, pycdlib, hexdump, "
            "and the PyInstaller bootloader. Select <i>Licenses and third-party notices</i> "
            "to read their complete notices and license terms.</p>"
        )
        layout.addWidget(description)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        licenses = buttons.addButton(
            "Licenses and third-party notices…", QDialogButtonBox.ButtonRole.ActionRole
        )
        licenses.clicked.connect(self._show_licenses)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _show_licenses(self) -> None:
        LicensesDialog(self).exec()


class LicensesDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.documents = load_license_documents()
        self.setWindowTitle("Licenses and third-party notices")
        self.resize(940, 680)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "The list below covers the application and third-party components shipped in "
            "PS2OPLRipper.exe. Build- and test-only packages that are not shipped are excluded."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.component_list = QListWidget()
        self.component_list.setAccessibleName("Licensed components")
        self.component_list.addItem("Overview / distribution notices")
        for document in self.documents:
            self.component_list.addItem(document.title)
        self.license_text = QPlainTextEdit()
        self.license_text.setAccessibleName("License text")
        self.license_text.setReadOnly(True)
        self.license_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.license_text.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        splitter.addWidget(self.component_list)
        splitter.addWidget(self.license_text)
        splitter.setSizes([280, 660])
        layout.addWidget(splitter, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.component_list.currentRowChanged.connect(self._show_document)
        self.component_list.setCurrentRow(0)

    def _show_document(self, row: int) -> None:
        if row == 0:
            text = third_party_overview()
        elif 1 <= row <= len(self.documents):
            document: LicenseDocument = self.documents[row - 1]
            text = document.display_text()
        else:
            text = ""
        self.license_text.setPlainText(text)
        self.license_text.moveCursor(self.license_text.textCursor().MoveOperation.Start)


class EraseConfirmationDialog(QDialog):
    def __init__(self, disk: PhysicalDisk, parent=None) -> None:
        super().__init__(parent)
        self.disk = disk
        self.setWindowTitle("Confirm USB drive initialization")
        self.setMinimumWidth(620)
        layout = QVBoxLayout(self)
        warning = QLabel(
            "<b>This permanently erases every partition and file on the selected physical disk.</b>"
        )
        warning.setStyleSheet("color: #a40000; font-size: 14px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        mounts = (
            ", ".join(point for volume in disk.volumes for point in volume.mount_points) or "None"
        )
        filesystems = ", ".join(volume.filesystem or "Unknown" for volume in disk.volumes) or "None"
        partitions = (
            "\n".join(
                f"Partition {part.number}: {human_size(part.length)} — {part.type_description}"
                for part in disk.partitions
            )
            or "No readable partitions"
        )
        details = QLabel(
            f"Physical disk: <b>{disk.physical_name}</b><br>"
            f"Manufacturer: {disk.manufacturer or 'Unknown'}<br>"
            f"Model: {disk.model}<br>"
            f"Serial: {disk.serial or 'Unavailable'}<br>"
            f"Capacity: {human_size(disk.capacity)} ({disk.capacity:,} bytes)<br>"
            f"Device class: {'Removable' if disk.removable else 'Fixed'}<br>"
            f"Drive letters: {mounts}<br>"
            f"Filesystems: {filesystems}<br>"
            f"Partition table: {disk.partition_style.name}<br><br>"
            f"Partitions to erase:<br>{partitions.replace(chr(10), '<br>')}"
        )
        details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(details)
        expected = expected_erase_confirmation(disk)
        layout.addWidget(QLabel(f"Type <b>{expected}</b> to continue:"))
        self.confirmation = QLineEdit()
        self.confirmation.setAccessibleName("Destructive operation confirmation")
        layout.addWidget(self.confirmation)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.ok_button = self.buttons.button(QDialogButtonBox.Ok)
        self.ok_button.setText("Erase and initialize")
        self.ok_button.setEnabled(False)
        self.confirmation.textChanged.connect(
            lambda value: self.ok_button.setEnabled(value.strip().upper() == expected)
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)


class AdvancedSettingsDialog(QDialog):
    def __init__(self, settings: QSettings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Advanced settings")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        directory_row = QHBoxLayout()
        default_temp = str(Path.home() / "AppData" / "Local" / "Temp")
        self.temp_directory = QLineEdit(settings.value("rip/tempDirectory", default_temp, str))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        directory_row.addWidget(self.temp_directory)
        directory_row.addWidget(browse)
        form.addRow("Temporary directory", directory_row)
        self.chunk = QSpinBox()
        self.chunk.setRange(1, 256)
        self.chunk.setValue(settings.value("rip/chunkSectors", 32, int))
        self.chunk.setSuffix(" sectors")
        form.addRow("Optical read chunk", self.chunk)
        self.retries = QSpinBox()
        self.retries.setRange(1, 32)
        self.retries.setValue(settings.value("rip/maxRetries", 8, int))
        form.addRow("Maximum single-sector retries", self.retries)
        self.retain_image = QCheckBox("Retain temporary ISO after a successful install")
        self.retain_image.setChecked(settings.value("rip/retainImage", False, bool))
        form.addRow("", self.retain_image)
        self.retain_archive = QCheckBox("Retain archival BIN/CUE for PS2 CDs")
        self.retain_archive.setChecked(settings.value("rip/retainArchive", False, bool))
        form.addRow("", self.retain_archive)
        self.auto_eject = QCheckBox("Eject the disc after successful verification")
        self.auto_eject.setChecked(settings.value("rip/autoEject", False, bool))
        form.addRow("", self.auto_eject)
        layout.addLayout(form)
        note = QLabel(
            "SHA-256 and structural ISO validation are always enabled. Dangerous raw-disk parameters "
            "are intentionally not configurable."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Select temporary directory", self.temp_directory.text()
        )
        if selected:
            self.temp_directory.setText(selected)

    def accept(self) -> None:
        self.settings.setValue("rip/tempDirectory", self.temp_directory.text())
        self.settings.setValue("rip/chunkSectors", self.chunk.value())
        self.settings.setValue("rip/maxRetries", self.retries.value())
        self.settings.setValue("rip/retainImage", self.retain_image.isChecked())
        self.settings.setValue("rip/retainArchive", self.retain_archive.isChecked())
        self.settings.setValue("rip/autoEject", self.auto_eject.isChecked())
        self.settings.sync()
        super().accept()


def rip_settings(settings: QSettings) -> RipSettings:
    default_temp = Path.home() / "AppData" / "Local" / "Temp"
    return RipSettings(
        temporary_directory=Path(settings.value("rip/tempDirectory", str(default_temp), str)),
        read_chunk_sectors=settings.value("rip/chunkSectors", 32, int),
        maximum_retries=settings.value("rip/maxRetries", 8, int),
        retain_temporary_image=settings.value("rip/retainImage", False, bool),
        retain_archival_bin_cue=settings.value("rip/retainArchive", False, bool),
    )

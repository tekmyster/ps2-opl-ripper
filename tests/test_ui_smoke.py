import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ps2ripper.core.models import PartitionInfo, PartitionStyle, PhysicalDisk, VolumeInfo
from ps2ripper.licensing import load_license_documents
from ps2ripper.ui.dialogs import AboutDialog, LicensesDialog
from ps2ripper.ui.main_window import MainWindow


def _ui_disk(mount: str, *, number: int = 3, ready: bool = True) -> PhysicalDisk:
    style = PartitionStyle.MBR if ready else PartitionStyle.GPT
    return PhysicalDisk(
        number=number,
        device_path=rf"\\.\PhysicalDrive{number}",
        instance_id=f"USBSTOR\\TEST_{number}",
        model="Test PS2 drive",
        manufacturer="Test",
        bus_type="USB",
        capacity=64 * 1024**3,
        usb=True,
        partition_style=style,
        partitions=(PartitionInfo(1, 1024 * 1024, 63 * 1024**3, style),),
        volumes=(
            VolumeInfo(
                f"\\\\?\\Volume{{test-{number}}}\\",
                (mount,),
                "exFAT" if ready else "NTFS",
                writable=True,
                disk_numbers=(number,),
            ),
        ),
    )


def test_main_window_constructs_without_starting_event_loop():
    app = QApplication.instance() or QApplication([])
    assert app is not None
    window = MainWindow(Path("PS2Ripper-test.log"))
    assert "PS2 OPL Ripper" in window.windowTitle()
    menus = [action.text() for action in window.menuBar().actions()]
    assert "Help" in menus
    window.deleteLater()


def test_about_and_license_dialogs_include_runtime_inventory():
    app = QApplication.instance() or QApplication([])
    assert app is not None
    about = AboutDialog()
    assert about.windowTitle() == "About PS2 OPL Ripper"
    licenses = LicensesDialog()
    identifiers = {document.identifier for document in load_license_documents()}
    assert identifiers == {
        "ps2ripper",
        "fattools",
        "qt-for-python",
        "pycdlib",
        "hexdump",
        "cpython",
        "pyinstaller",
    }
    assert licenses.component_list.count() == len(identifiers) + 1
    for row in range(licenses.component_list.count()):
        licenses.component_list.setCurrentRow(row)
        assert licenses.license_text.toPlainText().strip()
        assert "could not be loaded" not in licenses.license_text.toPlainText()
    licenses.deleteLater()
    about.deleteLater()


def test_ready_drive_is_detected_and_reformat_defaults_off(tmp_path):
    app = QApplication.instance() or QApplication([])
    assert app is not None
    window = MainWindow(Path("PS2Ripper-test.log"))
    ready = _ui_disk(str(tmp_path))
    window.disks = (ready,)
    window.disk_combo.addItem("test")
    window._show_disk()

    assert not window.ready_drive_banner.isHidden()
    assert window.ready_drive_banner.text() == "<b>PS2 READY DRIVE DETECTED</b>"
    assert not window.reformat_checkbox.isChecked()
    assert window.prepare_button.text() == "Use Existing PS2 Drive"

    window.reformat_checkbox.setChecked(True)
    assert window.prepare_button.text() == "Reformat Selected Drive"
    window.deleteLater()


def test_existing_ready_drive_is_reused_without_deleting_files(tmp_path):
    app = QApplication.instance() or QApplication([])
    assert app is not None
    existing_game = tmp_path / "DVD" / "SLUS_000.00.Existing Game.iso"
    existing_game.parent.mkdir()
    existing_game.write_bytes(b"existing game data")
    window = MainWindow(Path("PS2Ripper-test.log"))
    ready = _ui_disk(str(tmp_path))
    window.disks = (ready,)
    window.disk_combo.addItem("test")
    window._show_disk()
    window.refresh_optical = lambda: None

    window.prepare_selected_disk()

    assert window.opl_root == tmp_path
    assert existing_game.read_bytes() == b"existing game data"
    assert (tmp_path / "CD").is_dir()
    assert "No formatting was performed" in window.progress_label.text()
    window.deleteLater()


def test_changing_drive_clears_reformat_selection(tmp_path):
    app = QApplication.instance() or QApplication([])
    assert app is not None
    window = MainWindow(Path("PS2Ripper-test.log"))
    ready = _ui_disk(str(tmp_path), number=3)
    incompatible = _ui_disk(str(tmp_path), number=4, ready=False)
    window.disks = (ready, incompatible)
    window.disk_combo.addItems(["ready", "incompatible"])
    window._show_disk()
    window.reformat_checkbox.setChecked(True)

    window.disk_combo.setCurrentIndex(1)

    assert not window.reformat_checkbox.isChecked()
    assert window.ready_drive_banner.isHidden()
    assert window.prepare_button.text() == "Review Drive Requirements"
    window.deleteLater()

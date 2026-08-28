import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ps2ripper.licensing import load_license_documents
from ps2ripper.ui.dialogs import AboutDialog, LicensesDialog
from ps2ripper.ui.main_window import MainWindow


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

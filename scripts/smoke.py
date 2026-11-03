"""Exercise the installed subset in an isolated environment."""
import importlib
import importlib.util
import os
from importlib.metadata import distribution
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main() -> None:
    import PySide6
    from PySide6 import QtCore, QtGui, QtSvg, QtWidgets, _config

    package = distribution("ok-pyside-minimal")
    assert package.requires == [f"shiboken6=={PySide6.__version__}"], package.requires
    assert not package.entry_points
    assert set(_config.built_modules) == {"Core", "Gui", "Widgets", "Svg"}

    for module in _config.built_modules:
        importlib.import_module("PySide6.Qt" + module)
    for module in (
        "QtQuick", "QtQuickWidgets", "QtQuickControls2", "QtQml", "QtQmlFeatures",
        "QtOpenGL", "QtOpenGLWidgets", "QtSql", "QtDesigner", "QtPrintSupport",
        "QtHelp", "QtUiTools", "QtLabsStyleKit",
        "QtTest", "QtConcurrent", "QtDBus", "QtXml", "QtSvgWidgets", "QtNetwork",
    ):
        assert importlib.util.find_spec("PySide6." + module) is None, module
    app = QtWidgets.QApplication([])
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    layout.addWidget(QtWidgets.QLabel("ok-pyside-minimal"))
    widget.resize(240, 80)
    widget.show()
    app.processEvents()
    assert not widget.grab().isNull()
    image = QtGui.QImage(16, 16, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.red)
    assert not image.isNull()
    assert QtSvg.QSvgRenderer(b'<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4"/>').isValid()
    # Exercise the SVG image and icon plugins as well as the direct renderer.
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4"><rect width="4" height="4" fill="red"/></svg>'
    assert not QtGui.QImage.fromData(svg, "SVG").isNull()
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        icon_path = Path(tmp) / "icon.svg"
        icon_path.write_bytes(svg)
        assert not QtGui.QIcon(str(icon_path)).pixmap(16, 16).isNull()
    assert Path(PySide6.__file__).exists()
    widget.close()
    print(f"Smoke test passed: PySide6 {PySide6.__version__}; modules={_config.built_modules}")


if __name__ == "__main__":
    main()

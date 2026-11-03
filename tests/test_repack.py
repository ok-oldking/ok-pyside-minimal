import base64
import csv
import hashlib
import io
import json
import zipfile
from email.parser import BytesParser

import pytest

from scripts import native, release
from scripts.policy import remove
from scripts.repack import patch_assignment, repack


@pytest.mark.parametrize("path", [
    "PySide6/QtQuick.abi3.so", "PySide6/QtQmlFeatures.pyi", "PySide6/QtOpenGL.pyd",
    "PySide6/Qt6Sql.dll", "PySide6/Qt/lib/libQt6PrintSupport.so.6",
    "PySide6/Qt/lib/QtDesigner.framework/Versions/A/QtDesigner",
    "PySide6/Qt/qml/QtQuick/Foo.qml", "PySide6/qml/QtQml/qmldir",
    "PySide6/plugins/sqldrivers/qsqlite.dll", "PySide6/Qt/plugins/designer/plugin.so",
    "PySide6/Designer.app/Contents/MacOS/Designer", "PySide6/opengl32sw.dll",
    "PySide6/lib/libpyside6qml.abi3.so.6.12", "PySide6/QtHelp.pyd",
    "PySide6/QtUiTools.pyd", "PySide6/Qt6LabsStyleKit.dll", "PySide6/qmlformat.exe",
    "PySide6/typesystems/typesystem_quick.xml", "PySide6/glue/qtqml.cpp",
    "PySide6/Qt/libexec/qmlcachegen", "PySide6/lupdate.exe", "PySide6/linguist.exe",
    "PySide6/include/PySide6/pysideqml.h", "PySide6/Qt/lib/libQt6EglFSDeviceIntegration.so.6",
    "PySide6/Qt6Test.dll", "PySide6/QtTest.pyd", "PySide6/QtConcurrent.pyi",
    "PySide6/QtDBus.abi3.so", "PySide6/Qt6DBus.dll", "PySide6/QtXml.pyd",
    "PySide6/Qt6Network.dll", "PySide6/QtSvgWidgets.pyd", "PySide6/uic.exe",
    "PySide6/Qt/lib/cmake/Qt6Core/Qt6CoreConfig.cmake", "PySide6/Qt/translations/qt_en.qm",
    "PySide6/translations/qt_en.qm", "PySide6/scripts/pyside_tool.py",
    "PySide6/plugins/tls/qopensslbackend.dll", "PySide6/plugins/imageformats/qtiff.dll",
    "PySide6/metatypes/qt6core_metatypes.json", "PySide6/pyside6.abi3.lib",
    "PySide6/Qt/lib/QtDBus.framework/Headers/QtDBus.h",
])
def test_excluded_paths(path):
    assert remove(path)


@pytest.mark.parametrize("path", [
    "PySide6/QtCore.abi3.so", "PySide6/QtGui.pyd", "PySide6/Qt6Widgets.dll",
    "PySide6/Qt/lib/QtSvg.framework/Versions/A/QtSvg",
    "PySide6/plugins/platforms/qwindows.dll", "PySide6/Qt/plugins/imageformats/libqsvg.so",
    "PySide6/Qt/lib/libQt6WaylandClient.so.6", "PySide6/Qt/lib/libQt6DBus.so.6",
    "PySide6/Qt/lib/QtDBus.framework/Versions/A/QtDBus",
])
def test_retained_paths(path):
    assert not remove(path)


def test_native_dependency_failure_and_plugin_pruning(monkeypatch):
    monkeypatch.setattr(native, "dependencies", lambda data: set(data.decode().split()))
    files = {"PySide6/core.dll": b"system.dll", "PySide6/plugins/foo.dll": b"Qt6Qml.dll"}
    assert native.prune_broken_plugins(files, {"qt6qml.dll"}) == ["PySide6/plugins/foo.dll"]
    with pytest.raises(ValueError, match="Required binaries"):
        native.prune_broken_plugins({"PySide6/core.dll": b"Qt6Qml.dll"}, {"qt6qml.dll"})


def test_assignment_fails_closed():
    with pytest.raises(ValueError, match="Upstream format changed"):
        patch_assignment("x = 1\n", "built_modules", [])


def test_complete_wheel_transformation(tmp_path):
    source = tmp_path / "pyside6_essentials-6.12.0-cp310-abi3-win_amd64.whl"
    di = "pyside6_essentials-6.12.0.dist-info"
    files = {
        **{f"PySide6/Qt{m}.pyd": b"fake binary" for m in ["Core", "Gui", "Widgets", "Qml", "Sql"]},
        "PySide6/_config.py": b'built_modules = list(x for x in "Core;Qml".split(";"))\nversion = "6.12.0"\n',
        "PySide6/__init__.py": b'__pre_all__ = ["QtCore", "QtQml"]\n__version__ = "6.12.0"\n',
        "PySide6/PySide6_Essentials.json": b'{"Core": [], "Qml": []}',
        di + "/METADATA": b"Metadata-Version: 2.4\nName: PySide6_Essentials\nVersion: 6.12.0\nSummary: Qt\nRequires-Python: >=3.10\nRequires-Dist: shiboken6==6.12.0\nRequires-Dist: numpy\nRequires-Dist: setuptools\nLicense: LGPL-3.0-only\n\nUpstream\n",
        di + "/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: cp310-abi3-win_amd64\n",
        di + "/entry_points.txt": b"[console_scripts]\npyside6-qml = bad:qml\npyside6-uic = tools:uic\n",
        di + "/RECORD": b"old-record",
    }
    with zipfile.ZipFile(source, "w") as z:
        for name, data in files.items():
            info = zipfile.ZipInfo(name)
            info.external_attr = 0o100755 << 16
            z.writestr(info, data)
    target, report = repack(source, tmp_path / "out", {"sha256": "example"}, "6.12.0.post1")
    assert target.name == "ok_pyside_minimal-6.12.0.post1-cp310-abi3-win_amd64.whl"
    with zipfile.ZipFile(target) as z:
        assert not any(remove(n) for n in z.namelist())
        ndi = "ok_pyside_minimal-6.12.0.post1.dist-info"
        meta = BytesParser().parsebytes(z.read(ndi + "/METADATA"))
        assert meta["Name"] == "ok-pyside-minimal"
        assert meta["Requires-Dist"] == "shiboken6==6.12.0"
        assert meta.get_all("Requires-Dist") == ["shiboken6==6.12.0"]
        assert meta["Version"] == "6.12.0.post1"
        assert ndi + "/entry_points.txt" not in z.namelist()
        scope = {}
        exec(z.read("PySide6/_config.py"), scope)
        assert scope["built_modules"] == ["Core", "Gui", "Widgets"]
        assert z.read("PySide6/QtCore.pyd") == files["PySide6/QtCore.pyd"]
        assert z.getinfo("PySide6/QtCore.pyd").external_attr == 0o100755 << 16
        rows = list(csv.reader(io.StringIO(z.read(ndi + "/RECORD").decode())))
        assert {row[0] for row in rows} == set(z.namelist())
        for name, digest, length in rows:
            if not digest:
                assert name == ndi + "/RECORD"
                continue
            data = z.read(name)
            assert len(data) == int(length)
            assert digest == "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        assert json.loads(z.read(ndi + "/upstream.json"))["upstream_version"] == "6.12.0"
    assert report["modules"] == ["Core", "Gui", "Widgets"]


def test_plan_repairs_partial_upload(monkeypatch):
    file = {"filename": "pyside6_essentials-6.12.0-cp310-abi3-win_amd64.whl", "packagetype": "bdist_wheel", "yanked": False}
    monkeypatch.setattr(release, "upstream", lambda version=None: {"releases": {"6.12.0": [], "6.13.0rc1": []}, "urls": [file]})
    monkeypatch.setattr(release, "fetch_json", lambda *a, **kw: {"urls": []})
    assert release.make_plan()["version"] == "6.12.0.post1"
    monkeypatch.setattr(release, "fetch_json", lambda *a, **kw: {"urls": [{"filename": release.output_name(file["filename"], "6.12.0.post1")}]})
    assert release.make_plan()["available"] == "false"


def test_deleted_release_uses_unused_revision():
    assert release.release_version("6.12.0") == "6.12.0.post1"
    assert release.release_version("6.12.0", 2) == "6.12.0.post2"
    assert release.release_version("6.12.1") == "6.12.1"
    with pytest.raises(ValueError):
        release.release_version("6.12.0", -1)


def test_unknown_platform_and_yanked_release_fail_closed():
    with pytest.raises(ValueError, match="No test runner"):
        release.runner("new-platform.whl")
    with pytest.raises(ValueError, match="yanked"):
        release.wheel_files({"urls": [{"packagetype": "bdist_wheel", "yanked": True}]})

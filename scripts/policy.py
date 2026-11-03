"""Conservative pruning policy shared by the builder and artifact checks."""
import re
from pathlib import PurePosixPath

MODULES = {
    "Core", "Gui", "Widgets", "Network", "Concurrent", "DBus", "Xml",
    "Test", "Svg", "SvgWidgets",
}
# Help links to QtSql. LabsStyleKit and Lottie use Qt Quick/QML.
REMOVED = re.compile(
    r"(?:lib)?Qt(?:6)?(?:Quick\w*|Qml\w*|OpenGL\w*|Sql|Designer\w*|"
    r"PrintSupport|Help|UiTools|Labs\w*|Lottie\w*|LanguageServer|JsonRpc|"
    r"WaylandCompositor|WaylandEglCompositorHwIntegration|EglFS\w*)(?=[./_-]|$)", re.I
)
PLUGIN_GROUPS = {
    "designer", "printsupport", "sqldrivers", "qmltooling", "scenegraph",
    "vectorimageformats", "renderers", "renderplugins", "wayland-graphics-integration-server",
}
REMOVED_TOOLS = {
    "assistant", "designer", "qml", "qmlcachegen", "qmlformat", "qmlimportscanner",
    "qmllint", "qmlls", "qmltyperegistrar", "svgtoqml", "qsb", "balsam", "balsamui",
    "qmlpreview", "qmlprofiler", "qmltestrunner", "linguist", "lupdate", "lrelease",
}
ENTRY_POINTS = {"rcc", "uic", "genpyi", "metaobjectdump", "qtpy2cpp"}


def remove(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if not parts or parts[0] != "PySide6":
        return False
    if any(REMOVED.match(p) for p in parts):
        return True
    if any(p.lower() in {"qml", "qmltypes"} for p in parts[1:]):
        return True
    if "plugins" in parts:
        idx = parts.index("plugins")
        if len(parts) > idx + 1 and parts[idx + 1] in PLUGIN_GROUPS:
            return True
    name = parts[-1].lower()
    if name in {"opengl32sw.dll"} or "pyside6qml" in name or "pysideqml" in name:
        return True
    if any(p.lower().removesuffix(".app") in REMOVED_TOOLS for p in parts[1:]):
        return True
    if name.removesuffix(".exe") in REMOVED_TOOLS:
        return True
    if name.startswith(("qml", "qtqml", "qtquick", "qtdeclarative", "qt_help", "assistant", "designer")):
        return True
    # Developer assets for removed modules (typesystem_qml.xml, qtqml.cpp, etc.).
    if any(x in name for x in ("opengl", "printsupport", "qtsql", "qt_help")):
        return True
    if name.startswith("typesystem_"):
        module = name[len("typesystem_"):].split(".")[0]
        return module not in {m.lower() for m in MODULES}
    if "include" in parts:
        for part in parts[parts.index("include") + 1:]:
            if part.startswith("Qt") and part[2:] not in MODULES:
                return True
    # Deployment/project generators assume the complete upstream distribution.
    if "scripts" in parts and any(p.startswith(("deploy", "project")) for p in parts):
        return True
    return False

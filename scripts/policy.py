"""Conservative pruning policy shared by the builder and artifact checks."""
import re
from pathlib import PurePosixPath

MODULES = {"Core", "Gui", "Widgets", "Svg"}
# Help links to QtSql. LabsStyleKit and Lottie use Qt Quick/QML.
REMOVED = re.compile(
    r"(?:lib)?Qt(?:6)?(?:Quick\w*|Qml\w*|OpenGL\w*|Sql|Designer\w*|"
    r"PrintSupport|Help|UiTools|Network|Concurrent|Test|Xml|SvgWidgets|Labs\w*|Lottie\w*|LanguageServer|JsonRpc|"
    r"WaylandCompositor|WaylandEglCompositorHwIntegration|EglFS\w*)(?=[./_-]|$)", re.I
)
PLUGIN_GROUPS = {
    "designer", "printsupport", "sqldrivers", "qmltooling", "scenegraph",
    "vectorimageformats", "renderers", "renderplugins", "wayland-graphics-integration-server",
    "tls", "networkaccess", "networkinformation",
}
REMOVED_TOOLS = {
    "assistant", "designer", "qml", "qmlcachegen", "qmlformat", "qmlimportscanner",
    "qmllint", "qmlls", "qmltyperegistrar", "svgtoqml", "qsb", "balsam", "balsamui",
    "qmlpreview", "qmlprofiler", "qmltestrunner", "linguist", "lupdate", "lrelease",
    "uic", "rcc",
}
IMAGE_PLUGINS = {"qgif", "qicns", "qico", "qjpeg", "qsvg", "qwebp"}


def remove(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if not parts or parts[0] != "PySide6":
        return False
    if any(p in {"include", "doc", "glue", "typesystems", "scripts", "cmake", "metatypes",
                 "translations", "__pycache__", "libexec", "bin", "Headers", "Modules"} for p in parts[1:]):
        return True
    # QtGui requires the native DBus library on Unix; no Python DBus API is kept.
    if any(re.match(r"(?:lib)?Qt(?:6)?DBus(?=[./_-]|$)", p, re.I) for p in parts):
        return not ("QtDBus.framework" in parts or parts[-1].startswith("libQt6DBus.so"))
    if any(REMOVED.match(p) for p in parts):
        return True
    if any(p.lower() in {"qml", "qmltypes"} for p in parts[1:]):
        return True
    if "plugins" in parts:
        idx = parts.index("plugins")
        if len(parts) > idx + 1 and parts[idx + 1] in PLUGIN_GROUPS:
            return True
        if len(parts) > idx + 2 and parts[idx + 1] == "imageformats":
            plugin = parts[-1].removeprefix("lib").split(".")[0]
            return plugin not in IMAGE_PLUGINS
    name = parts[-1].lower()
    if name.endswith((".lib", ".a", ".prl", ".cmake")) or name == "generate_pyi.py":
        return True
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
    return False

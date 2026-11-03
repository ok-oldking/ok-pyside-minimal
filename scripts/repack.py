"""Transform an official wheel, retaining native binaries byte for byte."""
import ast
import base64
import configparser
import csv
import hashlib
import io
import json
import re
import zipfile
from email import policy
from email.parser import Parser
from pathlib import Path

from packaging.utils import parse_wheel_filename

from scripts.native import identity, prune_broken_plugins
from scripts.policy import ENTRY_POINTS, MODULES, remove

PROJECT = "ok-pyside-minimal"
ROOT = Path(__file__).resolve().parents[1]


def normalized(data: bytes) -> str:
    return data.decode("utf-8").replace("\r\r\n", "\n").replace("\r\n", "\n")


def patch_assignment(text: str, name: str, value: object) -> str:
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            lines[node.lineno - 1:node.end_lineno] = [f"{name} = {value!r}\n"]
            return "".join(lines)
    raise ValueError(f"Upstream format changed: no assignment for {name}")


def repack(source: Path, output: Path, provenance: dict, version: str | None = None) -> tuple[Path, dict]:
    name, upstream_version, _, tags = parse_wheel_filename(source.name)
    if name != "pyside6-essentials":
        raise ValueError(f"Not an Essentials wheel: {source}")
    version = version or str(upstream_version)
    suffix = source.name.split("-", 2)[2]
    dist_info = f"ok_pyside_minimal-{version}.dist-info"
    with zipfile.ZipFile(source) as wheel:
        infos = {x.filename: x for x in wheel.infolist() if not x.is_dir()}
        old_info = [x for x in infos if x.endswith(".dist-info/METADATA")]
        if len(old_info) != 1:
            raise ValueError("Expected exactly one upstream metadata directory")
        old_info = old_info[0].rsplit("/", 1)[0]
        removed_names = {n for n in infos if remove(n)}
        files = {n: wheel.read(n) for n in infos if n not in removed_names and not n.startswith(old_info + "/")}
        removed_native = {identity(n) for n in removed_names}
        dropped_plugins = prune_broken_plugins(files, removed_native)
        removed_names.update(dropped_plugins)
        modules = sorted({
            n.split("/")[1].split(".")[0][2:] for n in files
            if re.match(r"^PySide6/Qt\w+\.(?:pyd|.*so)$", n)
        })
        if not {"Core", "Gui", "Widgets"} <= set(modules) or not set(modules) <= MODULES:
            raise ValueError(f"Unexpected runtime module set: {modules}")
        files["PySide6/_config.py"] = patch_assignment(
            normalized(files["PySide6/_config.py"]), "built_modules", modules
        ).encode()
        init = normalized(files["PySide6/__init__.py"])
        variable = "__pre_all__" if "__pre_all__ =" in init else "__all__"
        files["PySide6/__init__.py"] = patch_assignment(init, variable, ["Qt" + m for m in modules]).encode()
        manifest_path = "PySide6/PySide6_Essentials.json"
        if manifest_path in files:
            upstream_plugins = json.loads(normalized(files[manifest_path]))
            files[manifest_path] = (json.dumps({k: v for k, v in upstream_plugins.items() if k in modules}, indent=2) + "\n").encode()
        meta = Parser(policy=policy.default).parsestr(normalized(wheel.read(old_info + "/METADATA")))
        meta.replace_header("Name", PROJECT)
        meta.replace_header("Version", version)
        meta.replace_header("Summary", "Unofficial PySide6 Essentials subset for Qt Widgets applications")
        for field in ("Project-URL", "Dynamic", "License-File"):
            if field in meta:
                del meta[field]
        meta["Project-URL"] = "Repository, https://github.com/ok-oldking/ok-pyside-minimal"
        meta["Project-URL"] = "Upstream, https://code.qt.io/cgit/pyside/pyside-setup.git/"
        meta.set_payload((ROOT / "README.md").read_text(encoding="utf-8"))
        for n in infos:
            if n.startswith(old_info + "/licenses/"):
                target = n.replace(old_info, dist_info, 1)
                files[target] = wheel.read(n)
        for license_file in (ROOT / "licenses").glob("*.txt"):
            files[f"{dist_info}/licenses/{license_file.name}"] = license_file.read_bytes()
        files[f"{dist_info}/licenses/NOTICE.txt"] = (ROOT / "NOTICE").read_bytes()
        files[f"{dist_info}/licenses/MIT-tooling.txt"] = (ROOT / "LICENSE").read_bytes()
        for n in sorted(files):
            if n.startswith(dist_info + "/licenses/"):
                meta["License-File"] = n.split("/licenses/", 1)[1]
        files[dist_info + "/METADATA"] = meta.as_string(policy=policy.default.clone(linesep="\n", max_line_length=0)).encode("utf-8")
        files[dist_info + "/WHEEL"] = wheel.read(old_info + "/WHEEL")
        files[dist_info + "/top_level.txt"] = b"PySide6\n"
        config = configparser.ConfigParser()
        config.read_string(normalized(wheel.read(old_info + "/entry_points.txt")))
        for key in list(config["console_scripts"]):
            if key.removeprefix("pyside6-") not in ENTRY_POINTS:
                del config["console_scripts"][key]
        buf = io.StringIO()
        config.write(buf)
        files[dist_info + "/entry_points.txt"] = buf.getvalue().encode()
        report = {
            "project": PROJECT, "version": version, "upstream_version": str(upstream_version),
            "upstream": provenance, "modules": modules,
            "removed": sorted(removed_names), "dependency_pruned_plugins": dropped_plugins,
            "source_archives": {
                "pyside": f"https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-{upstream_version}-src/",
                "qt": f"https://download.qt.io/official_releases/qt/{upstream_version.major}.{upstream_version.minor}/{upstream_version}/single/",
            },
        }
        files[dist_info + "/upstream.json"] = (json.dumps(report, indent=2) + "\n").encode()
        record = io.StringIO(newline="")
        writer = csv.writer(record, lineterminator="\n")
        for n, data in sorted(files.items()):
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
            writer.writerow([n, "sha256=" + digest, len(data)])
        writer.writerow([dist_info + "/RECORD", "", ""])
        files[dist_info + "/RECORD"] = record.getvalue().encode()
        output.mkdir(parents=True, exist_ok=True)
        target = output / f"ok_pyside_minimal-{version}-{suffix}"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as result:
            for n, data in sorted(files.items()):
                info = zipfile.ZipInfo(n, date_time=(2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                # Preserve executable modes required by Unix tools and macOS frameworks.
                info.external_attr = infos[n].external_attr if n in infos else 0o100644 << 16
                result.writestr(info, data)
        report["original_bytes"] = source.stat().st_size
        report["wheel_bytes"] = target.stat().st_size
        report["wheel"] = target.name
        return target, report

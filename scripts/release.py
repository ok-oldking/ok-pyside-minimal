"""Discover official updates, verify downloads, and build release artifacts."""
import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from packaging.version import Version

from scripts.repack import PROJECT, repack

BASELINE = Version("6.12.0")
# PyPI permanently reserves filenames from deleted releases.
MINIMUM_REVISIONS = {"6.12.0": 1}


def release_version(upstream_version: str, revision: int = 0) -> str:
    if revision < 0:
        raise ValueError("Revision must be nonnegative")
    version = str(Version(upstream_version))
    revision = max(revision, MINIMUM_REVISIONS.get(version, 0))
    return version + (f".post{revision}" if revision else "")


def fetch_json(url: str, missing_ok: bool = False) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if missing_ok and exc.code == 404:
            return {}
        raise


def upstream(version: str | None = None) -> dict:
    path = f"/{version}" if version else ""
    return fetch_json(f"https://pypi.org/pypi/PySide6-Essentials{path}/json")


def runner(filename: str) -> str:
    for suffix, label in (
        ("win_amd64.whl", "windows-latest"), ("win_arm64.whl", "windows-11-arm"),
        ("aarch64.whl", "ubuntu-24.04-arm"), ("x86_64.whl", "ubuntu-24.04"),
        ("universal2.whl", "macos-15"),
    ):
        if filename.endswith(suffix):
            return label
    raise ValueError(f"No test runner configured for new upstream platform: {filename}")


def wheel_files(data: dict) -> list[dict]:
    files = [f for f in data["urls"] if f["packagetype"] == "bdist_wheel"]
    if not files or any(f["yanked"] for f in files):
        raise ValueError("Upstream release is empty or contains yanked wheels")
    return sorted(files, key=lambda f: f["filename"])


def output_name(filename: str, version: str) -> str:
    return f"ok_pyside_minimal-{version}-" + filename.split("-", 2)[2]


def make_plan(requested: str | None = None, revision: int = 0) -> dict:
    if revision < 0:
        raise ValueError("Revision must be nonnegative")
    index = upstream()
    versions = [Version(requested)] if requested else sorted(
        Version(v) for v in index["releases"]
        if Version(v) >= BASELINE and not Version(v).is_prerelease and not Version(v).is_devrelease
    )
    for candidate in versions:
        version = release_version(str(candidate), revision)
        data = upstream(str(candidate))
        files = wheel_files(data)
        existing = fetch_json(f"https://pypi.org/pypi/{PROJECT}/{version}/json", missing_ok=True)
        published = {f["filename"] for f in existing.get("urls", [])}
        expected = {output_name(f["filename"], version) for f in files}
        if expected <= published:
            continue
        # Include every wheel when repairing partial publication; upload is idempotent.
        return {
            "available": "true", "upstream_version": str(candidate), "version": version,
            "matrix": {"include": [{"filename": f["filename"], "runner": runner(f["filename"])} for f in files]},
        }
    return {"available": "false", "version": "", "upstream_version": "", "matrix": {"include": []}}


def download(file: dict, cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / file["filename"]
    expected = file["digests"]["sha256"]
    if target.exists():
        with target.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() == expected:
                return target
    url = file["url"]
    if not url.startswith("https://files.pythonhosted.org/"):
        raise ValueError(f"Unexpected upstream download host: {url}")
    temp = target.with_suffix(".partial")
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=120) as response, temp.open("wb") as stream:
        while block := response.read(1024 * 1024):
            stream.write(block)
            digest.update(block)
    if digest.hexdigest() != expected:
        temp.unlink()
        raise ValueError(f"SHA-256 mismatch for {target.name}")
    temp.replace(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--version")
    plan.add_argument("--revision", type=int, default=0)
    build = sub.add_parser("build")
    build.add_argument("--version", required=True, help="Official upstream version")
    build.add_argument("--revision", type=int, default=0)
    build.add_argument("--filename", help="Build one upstream wheel (default: all)")
    build.add_argument("--cache", type=Path, default=Path(".cache"))
    build.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    if args.command == "plan":
        result = make_plan(args.version, args.revision)
        print(json.dumps(result, indent=2))
        if path := os.environ.get("GITHUB_OUTPUT"):
            with open(path, "a", encoding="utf-8") as stream:
                for key, value in result.items():
                    stream.write(f"{key}={json.dumps(value) if isinstance(value, dict) else value}\n")
        return
    if args.revision < 0:
        parser.error("Revision must be nonnegative")
    data = upstream(args.version)
    files = wheel_files(data)
    if args.filename:
        files = [f for f in files if f["filename"] == args.filename]
        if not files:
            parser.error("Requested wheel is not part of the official release")
    version = release_version(args.version, args.revision)
    Path("reports").mkdir(exist_ok=True)
    for file in files:
        source = download(file, args.cache)
        target, report = repack(source, args.output, {
            "filename": file["filename"], "url": file["url"], "sha256": file["digests"]["sha256"],
        }, version=version)
        Path("reports", target.stem + ".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Built {target}: {report['original_bytes']:,} -> {report['wheel_bytes']:,} bytes", flush=True)


if __name__ == "__main__":
    main()

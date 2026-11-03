"""Inspect native load commands without executing foreign-platform code."""
import io
import re
import tempfile
from pathlib import Path


def identity(name: str) -> str:
    match = re.search(r"(Qt\w+)\.framework/", name)
    return (match.group(1) if match else name.rsplit("/", 1)[-1]).lower()


def dependencies(data: bytes) -> set[str]:
    if data.startswith(b"MZ"):
        import pefile
        pe = pefile.PE(data=data, fast_load=True)
        try:
            pe.parse_data_directories(directories=[1, 13])
            return {
                item.dll.decode("ascii")
                for group in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT")
                for item in getattr(pe, group, [])
            }
        finally:
            pe.close()
    if data.startswith(b"\x7fELF"):
        from elftools.elf.elffile import ELFFile
        elf = ELFFile(io.BytesIO(data))
        return {
            tag.needed for segment in elf.iter_segments()
            if segment.header.p_type == "PT_DYNAMIC"
            for tag in segment.iter_tags() if tag.entry.d_tag == "DT_NEEDED"
        }
    if data[:4] in {
        b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
        b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca",
    }:
        from macholib.MachO import MachO
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "binary"
            path.write_bytes(data)
            return {name for header in MachO(str(path)).headers for _, _, name in header.walkRelocatables()}
    return set()


def prune_broken_plugins(files: dict[str, bytes], removed: set[str]) -> list[str]:
    """Drop optional plugins transitively; fail if a core runtime would break."""
    dropped = []
    deps = {name: {identity(x) for x in dependencies(data)} for name, data in files.items()}
    while True:
        broken = {name: values & removed for name, values in deps.items() if values & removed}
        if not broken:
            return dropped
        plugins = [name for name in broken if "/plugins/" in name]
        if not plugins:
            raise ValueError(f"Required binaries depend on removed libraries: {broken}")
        for name in plugins:
            removed.add(identity(name))
            dropped.append(name)
            del files[name]
            del deps[name]

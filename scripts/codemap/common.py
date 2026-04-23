"""Shared utilities for codemap generation."""
from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path
from typing import Iterable, Iterator, Optional

try:
    import clang.cindex as ci  # type: ignore
except ImportError:
    print(
        "Error: libclang Python bindings not found.\n"
        "Install with: pip install libclang>=16",
        file=sys.stderr,
    )
    raise


DEFAULT_EXCLUDE_DIRS = {
    "third_party", "3rdparty", "external", "extern", "vendor",
    "build", "out", "cmake-build-debug", "cmake-build-release",
    ".git", ".svn", ".hg", ".vs", ".vscode", ".idea",
    "node_modules", "__pycache__", "target",
}

DEFAULT_HEADER_EXTS = (".h", ".hpp", ".hh", ".hxx", ".inl", ".ipp")
DEFAULT_SOURCE_EXTS = (".cpp", ".cc", ".cxx", ".c", ".mm", ".m")

DEFAULT_CONFIG = {
    "src_root": "src",
    "output_dir": "codemap",
    "module_depth": 1,
    "exclude_dirs": sorted(DEFAULT_EXCLUDE_DIRS),
    "compile_commands": None,
    "default_compile_args": ["-std=c++20", "-xc++"],
    "include_paths": [],
    "system_include_paths": [],
    "defines": [],
    "libclang_path": None,
    "layering_rules": {},
}


def load_config(config_path: Optional[Path]) -> dict:
    """Load config JSON with defaults filled in."""
    cfg = dict(DEFAULT_CONFIG)
    if config_path and config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg


def setup_libclang(path: Optional[str]) -> None:
    """Point libclang at a specific shared library if provided."""
    if path:
        ci.Config.set_library_file(path)


def load_compile_commands(path: Path) -> dict:
    """Load compile_commands.json into {absolute_file_path: filtered_args}."""
    with open(path, "r", encoding="utf-8") as f:
        entries = json.load(f)
    result: dict = {}
    for e in entries:
        directory = Path(e["directory"])
        file_path = (directory / e["file"]).resolve()
        if "arguments" in e:
            args = list(e["arguments"])
        else:
            args = shlex.split(e.get("command", ""))
        result[str(file_path)] = _filter_compile_args(args)
    return result


def _filter_compile_args(args: list) -> list:
    """Strip compiler binary, source files, and output flags."""
    if not args:
        return []
    filtered: list = []
    skip_next = False
    for i, a in enumerate(args):
        if i == 0:
            # Compiler path (e.g., /usr/bin/clang++). Skip.
            continue
        if skip_next:
            skip_next = False
            continue
        if a in ("-o", "-MF", "-MT", "-MQ"):
            skip_next = True
            continue
        if a in ("-c", "-MD", "-MMD", "-MP"):
            continue
        if a.endswith(DEFAULT_SOURCE_EXTS):
            continue
        filtered.append(a)
    return filtered


def build_compile_args(
    cfg: dict,
    file_path: Optional[Path] = None,
    compile_db: Optional[dict] = None,
) -> list:
    """Return libclang args. Prefers compile_commands.json when available."""
    if compile_db and file_path is not None:
        key = str(file_path.resolve())
        if key in compile_db:
            return list(compile_db[key])

    args = list(cfg.get("default_compile_args", []))
    for inc in cfg.get("include_paths", []):
        args.append(f"-I{inc}")
    for inc in cfg.get("system_include_paths", []):
        args.append(f"-isystem{inc}")
    for d in cfg.get("defines", []):
        args.append(f"-D{d}")
    return args


def iter_cpp_files(
    src_root: Path,
    exclude_dirs: Optional[Iterable[str]] = None,
    extensions: tuple = DEFAULT_HEADER_EXTS + DEFAULT_SOURCE_EXTS,
) -> Iterator[Path]:
    """Walk src_root yielding C/C++ files, skipping excluded directories."""
    exclude = set(exclude_dirs or DEFAULT_EXCLUDE_DIRS)
    for root, dirs, files in os.walk(src_root):
        dirs[:] = [d for d in dirs if d not in exclude]
        for f in files:
            if f.endswith(extensions):
                yield Path(root) / f


def resolve_module(
    file_path: Path,
    src_root: Path,
    depth: int = 1,
) -> Optional[str]:
    """Module name = first `depth` path segments under src_root."""
    try:
        rel = file_path.resolve().relative_to(src_root.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) <= depth:
        return None  # file lives at or above module level
    return "/".join(parts[:depth])


def clean_comment(raw: Optional[str]) -> str:
    """Strip /** */, //!, /// markers and doxygen tags, return plain text."""
    if not raw:
        return ""
    out_lines: list = []
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("/**"):
            s = s[3:]
        elif s.startswith("/*!"):
            s = s[3:]
        elif s.startswith("/*"):
            s = s[2:]
        if s.endswith("*/"):
            s = s[:-2]
        s = s.strip()
        if s.startswith("///"):
            s = s[3:].strip()
        elif s.startswith("//!"):
            s = s[3:].strip()
        elif s.startswith("//"):
            s = s[2:].strip()
        if s.startswith("*"):
            s = s[1:].strip()
        # Drop doxygen tag lines from the brief summary
        if s.startswith(("@param", "@return", "@brief", "@note", "@see",
                        "\\param", "\\return", "\\brief", "\\note", "\\see")):
            continue
        if s:
            out_lines.append(s)
    return " ".join(out_lines)


def first_sentence(text: str, max_len: int = 240) -> str:
    """Extract a short one-liner suitable for markdown bullets."""
    if not text:
        return ""
    for sep in (". ", "。 ", "。", "\n"):
        if sep in text:
            first = text.split(sep, 1)[0]
            if sep in (". ", "。 ", "。"):
                first = first + sep.strip()
            return first[:max_len].rstrip() + ("" if len(first) <= max_len else "...")
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "..."

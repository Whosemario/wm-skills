#!/usr/bin/env python3
"""Step 1: Generate per-module markdown skeleton from C++ headers via libclang.

Usage:
    python extract_skeleton.py --config codemap.json [-v]

Output:
    <output_dir>/skeleton/<module>.md
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import clang.cindex as ci
from clang.cindex import AccessSpecifier, CursorKind, TranslationUnit

from common import (
    DEFAULT_HEADER_EXTS,
    build_compile_args,
    clean_comment,
    first_sentence,
    iter_cpp_files,
    load_compile_commands,
    load_config,
    resolve_module,
    setup_libclang,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--config", type=Path, default=Path("codemap.json"))
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--module", type=str, default=None,
                   help="Only process one module (useful for incremental runs).")
    return p.parse_args()


def get_signature(cursor) -> str:
    """Build a readable function/method signature."""
    is_ctor_or_dtor = cursor.kind in (CursorKind.CONSTRUCTOR, CursorKind.DESTRUCTOR)
    rt = "" if is_ctor_or_dtor else (cursor.result_type.spelling or "")
    parts: list = []
    if cursor.kind == CursorKind.CXX_METHOD:
        if cursor.is_static_method():
            parts.append("static")
        if cursor.is_virtual_method():
            parts.append("virtual")
    if cursor.kind == CursorKind.DESTRUCTOR and cursor.is_virtual_method():
        parts.append("virtual")
    if rt:
        parts.append(rt)

    arg_strs = []
    for arg in cursor.get_arguments():
        t = arg.type.spelling
        n = arg.spelling
        arg_strs.append(f"{t} {n}".strip() if n else t)
    parts.append(f"{cursor.spelling}({', '.join(arg_strs)})")
    sig = " ".join(parts)

    if cursor.kind == CursorKind.CXX_METHOD:
        if cursor.is_const_method():
            sig += " const"
        if cursor.is_pure_virtual_method():
            sig += " = 0"
    return sig


def extract_class(cursor) -> dict:
    info = {
        "name": cursor.spelling,
        "kind": {
            CursorKind.CLASS_DECL: "class",
            CursorKind.STRUCT_DECL: "struct",
            CursorKind.CLASS_TEMPLATE: "template class",
        }.get(cursor.kind, "class"),
        "file": cursor.location.file.name if cursor.location.file else "",
        "line": cursor.location.line,
        "doc": clean_comment(cursor.raw_comment),
        "bases": [],
        "methods": [],
        "is_abstract": False,
    }
    try:
        info["is_abstract"] = cursor.is_abstract_record()
    except Exception:
        pass

    for c in cursor.get_children():
        if c.kind == CursorKind.CXX_BASE_SPECIFIER:
            info["bases"].append(c.type.spelling)
        elif c.kind in (CursorKind.CXX_METHOD,
                        CursorKind.CONSTRUCTOR,
                        CursorKind.DESTRUCTOR):
            if c.access_specifier == AccessSpecifier.PUBLIC:
                info["methods"].append({
                    "signature": get_signature(c),
                    "doc": first_sentence(clean_comment(c.raw_comment)),
                })
    return info


def visit(cursor, main_file_resolved: Path, collected: dict) -> None:
    """Recursively collect decls from the main file. Descends into namespaces."""
    for child in cursor.get_children():
        if not child.location.file:
            continue
        try:
            child_file = Path(child.location.file.name).resolve()
        except (OSError, ValueError):
            continue

        if child.kind == CursorKind.NAMESPACE:
            # Namespaces may open in many files; recurse regardless.
            visit(child, main_file_resolved, collected)
            continue

        if child_file != main_file_resolved:
            continue

        name = child.spelling or ""
        if name.startswith("_"):
            continue

        if child.kind in (CursorKind.CLASS_DECL,
                          CursorKind.STRUCT_DECL,
                          CursorKind.CLASS_TEMPLATE):
            if child.is_definition() and name:
                collected["classes"].append(extract_class(child))
        elif child.kind == CursorKind.FUNCTION_DECL:
            if name:
                collected["functions"].append({
                    "signature": get_signature(child),
                    "doc": first_sentence(clean_comment(child.raw_comment)),
                    "file": str(child_file),
                    "line": child.location.line,
                })
        elif child.kind == CursorKind.ENUM_DECL:
            if name:
                values = [v.spelling for v in child.get_children()
                          if v.kind == CursorKind.ENUM_CONSTANT_DECL]
                collected["enums"].append({
                    "name": name,
                    "doc": first_sentence(clean_comment(child.raw_comment)),
                    "values": values,
                    "file": str(child_file),
                    "line": child.location.line,
                })


def parse_header(
    index: ci.Index,
    header_path: Path,
    compile_args: list,
    verbose: bool = False,
) -> Optional[dict]:
    try:
        tu = index.parse(
            str(header_path),
            args=compile_args,
            options=(TranslationUnit.PARSE_SKIP_FUNCTION_BODIES
                     | TranslationUnit.PARSE_INCOMPLETE),
        )
    except ci.TranslationUnitLoadError as e:
        if verbose:
            print(f"  [WARN] parse failed: {header_path}: {e}", file=sys.stderr)
        return None

    if verbose:
        for diag in tu.diagnostics:
            if diag.severity >= ci.Diagnostic.Error:
                print(f"  [DIAG] {header_path}: {diag.spelling}",
                      file=sys.stderr)

    collected: dict = {"classes": [], "functions": [], "enums": []}
    visit(tu.cursor, header_path.resolve(), collected)
    return collected


def _rel(file_str: str, src_root: Path) -> str:
    try:
        return str(Path(file_str).resolve().relative_to(src_root.resolve()))
    except ValueError:
        return file_str


def render_markdown(module: str, data: dict, src_root: Path) -> str:
    lines: list = [
        f"# Module: `{module}`",
        "",
        "> _Auto-generated skeleton. Fill in the TODOs with architectural intent._",
        "",
        (f"**Stats:** {data['file_count']} header(s) &middot; "
         f"{len(data['classes'])} class(es) &middot; "
         f"{len(data['functions'])} free function(s) &middot; "
         f"{len(data['enums'])} enum(s)"),
        "",
        "## TODO (human review)",
        "",
        "- [ ] One-sentence module responsibility",
        "- [ ] What this module explicitly does **not** own",
        "- [ ] Threading / ownership / lifecycle rules",
        "- [ ] Invariants callers must uphold",
        "- [ ] Where to start for common change scenarios",
        "",
    ]

    if data["classes"]:
        lines += ["## Public Classes", ""]
        for c in sorted(data["classes"], key=lambda x: x["name"]):
            rel = _rel(c["file"], src_root)
            header = f"### `{c['name']}`"
            if c.get("is_abstract"):
                header += " &nbsp; _abstract_"
            if c["bases"]:
                header += f" &nbsp; : {', '.join(f'`{b}`' for b in c['bases'])}"
            lines.append(header)
            lines.append("")
            lines.append(f"<sub>`{rel}:{c['line']}`</sub>")
            lines.append("")
            if c["doc"]:
                lines.append(first_sentence(c["doc"], 300))
                lines.append("")
            if c["methods"]:
                shown = c["methods"][:20]
                lines.append("<details><summary>Public methods ("
                             f"{len(c['methods'])})</summary>\n")
                for m in shown:
                    doc = f" &mdash; {m['doc']}" if m["doc"] else ""
                    lines.append(f"- `{m['signature']}`{doc}")
                if len(c["methods"]) > 20:
                    lines.append(
                        f"- _... {len(c['methods']) - 20} more methods_")
                lines.append("")
                lines.append("</details>")
                lines.append("")

    if data["functions"]:
        lines += ["## Free Functions", ""]
        for f in sorted(data["functions"], key=lambda x: x["signature"]):
            rel = _rel(f["file"], src_root)
            doc = f" &mdash; {f['doc']}" if f["doc"] else ""
            lines.append(f"- `{f['signature']}`{doc}  ")
            lines.append(f"  <sub>`{rel}:{f['line']}`</sub>")
        lines.append("")

    if data["enums"]:
        lines += ["## Enums", ""]
        for e in sorted(data["enums"], key=lambda x: x["name"]):
            rel = _rel(e["file"], src_root)
            lines.append(f"### `{e['name']}` &nbsp; <sub>`{rel}:{e['line']}`</sub>")
            if e["doc"]:
                lines.append(f"> {e['doc']}")
            vals = ", ".join(f"`{v}`" for v in e["values"][:15])
            if len(e["values"]) > 15:
                vals += f", _... {len(e['values']) - 15} more_"
            lines.append(f"Values: {vals}")
            lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)
    setup_libclang(cfg.get("libclang_path"))

    src_root = Path(cfg["src_root"])
    if not src_root.exists():
        print(f"Error: src_root not found: {src_root}", file=sys.stderr)
        return 1

    output_dir = Path(cfg["output_dir"]) / "skeleton"
    output_dir.mkdir(parents=True, exist_ok=True)

    compile_db = None
    if cfg.get("compile_commands"):
        cc_path = Path(cfg["compile_commands"])
        if cc_path.exists():
            compile_db = load_compile_commands(cc_path)
            print(f"Loaded compile_commands.json: {len(compile_db)} entries")

    index = ci.Index.create()
    by_module: dict = defaultdict(
        lambda: {"classes": [], "functions": [], "enums": [], "file_count": 0}
    )

    headers = list(iter_cpp_files(src_root,
                                  set(cfg["exclude_dirs"]),
                                  DEFAULT_HEADER_EXTS))
    print(f"Parsing {len(headers)} header file(s)...")

    for i, h in enumerate(headers, 1):
        module = resolve_module(h, src_root, cfg["module_depth"])
        if not module:
            continue
        if args.module and module != args.module:
            continue
        if args.verbose or i % 50 == 0:
            print(f"  [{i}/{len(headers)}] {h}")

        file_args = build_compile_args(cfg, h, compile_db)
        result = parse_header(index, h, file_args, args.verbose)
        if result is None:
            continue

        bucket = by_module[module]
        bucket["classes"].extend(result["classes"])
        bucket["functions"].extend(result["functions"])
        bucket["enums"].extend(result["enums"])
        bucket["file_count"] += 1

    for module, data in sorted(by_module.items()):
        md = render_markdown(module, data, src_root)
        out_path = output_dir / f"{module.replace('/', '__')}.md"
        out_path.write_text(md, encoding="utf-8")
        print(f"  wrote {out_path} "
              f"({len(data['classes'])}c / {len(data['functions'])}f / "
              f"{len(data['enums'])}e)")

    print(f"\nDone. {len(by_module)} module(s) -> {output_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())

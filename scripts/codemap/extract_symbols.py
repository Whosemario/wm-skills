#!/usr/bin/env python3
"""Step 3: Extract structured public symbol inventory per module as JSON.

Output:
    <output_dir>/symbols/<module>.json   -- full inventory per module
    <output_dir>/symbols/_summary.json   -- per-module counts

Usage:
    python extract_symbols.py --config codemap.json [-v]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import clang.cindex as ci
from clang.cindex import AccessSpecifier, CursorKind, TranslationUnit

from common import (
    DEFAULT_HEADER_EXTS,
    build_compile_args,
    clean_comment,
    iter_cpp_files,
    load_compile_commands,
    load_config,
    resolve_module,
    setup_libclang,
)


INTERNAL_MARKERS = ("_Impl", "Internal", "Private", "Detail", "_internal")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--config", type=Path, default=Path("codemap.json"))
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--no-filter", action="store_true",
                   help="Disable filtering of names matching internal markers.")
    return p.parse_args()


def is_internal(name: str) -> bool:
    if not name:
        return True
    if name.startswith("_"):
        return True
    return any(m in name for m in INTERNAL_MARKERS)


def namespace_of(cursor) -> str:
    """Return `foo::bar::` style qualifier (without trailing ::) built from
    the cursor's semantic parents.
    """
    parts: list = []
    c = cursor.semantic_parent
    while c is not None and c.kind != CursorKind.TRANSLATION_UNIT:
        if c.kind == CursorKind.NAMESPACE and c.spelling:
            parts.append(c.spelling)
        elif c.kind in (CursorKind.CLASS_DECL,
                        CursorKind.STRUCT_DECL,
                        CursorKind.CLASS_TEMPLATE):
            if c.spelling:
                parts.append(c.spelling)
        c = c.semantic_parent
    return "::".join(reversed(parts))


def qualified(cursor) -> str:
    ns = namespace_of(cursor)
    return f"{ns}::{cursor.spelling}" if ns else cursor.spelling


def get_signature(cursor) -> str:
    is_ctor_or_dtor = cursor.kind in (CursorKind.CONSTRUCTOR, CursorKind.DESTRUCTOR)
    rt = "" if is_ctor_or_dtor else (cursor.result_type.spelling or "")
    arg_strs = []
    for arg in cursor.get_arguments():
        t = arg.type.spelling
        n = arg.spelling
        arg_strs.append(f"{t} {n}".strip() if n else t)
    return f"{rt} {cursor.spelling}({', '.join(arg_strs)})".strip()


def _access_name(access) -> str:
    # AccessSpecifier.PUBLIC -> "public"
    return str(access).split(".")[-1].lower() if access else "unknown"


def extract_class(cursor) -> dict:
    is_abstract = False
    try:
        is_abstract = cursor.is_abstract_record()
    except Exception:
        pass

    info: dict = {
        "name": cursor.spelling,
        "qualified_name": qualified(cursor),
        "kind": {
            CursorKind.CLASS_DECL: "class",
            CursorKind.STRUCT_DECL: "struct",
            CursorKind.CLASS_TEMPLATE: "class_template",
        }.get(cursor.kind, "class"),
        "is_abstract": is_abstract,
        "file": cursor.location.file.name if cursor.location.file else "",
        "line": cursor.location.line,
        "doc": clean_comment(cursor.raw_comment),
        "bases": [],
        "public_methods": [],
        "public_fields": [],
        "nested_types": [],
    }

    for c in cursor.get_children():
        if c.kind == CursorKind.CXX_BASE_SPECIFIER:
            info["bases"].append({
                "name": c.type.spelling,
                "access": _access_name(c.access_specifier),
            })
        elif c.kind == CursorKind.CXX_METHOD:
            if (c.access_specifier == AccessSpecifier.PUBLIC
                    and not is_internal(c.spelling)):
                info["public_methods"].append({
                    "name": c.spelling,
                    "signature": get_signature(c),
                    "is_static": c.is_static_method(),
                    "is_virtual": c.is_virtual_method(),
                    "is_pure_virtual": c.is_pure_virtual_method(),
                    "is_const": c.is_const_method(),
                    "doc": clean_comment(c.raw_comment),
                })
        elif c.kind == CursorKind.CONSTRUCTOR:
            if c.access_specifier == AccessSpecifier.PUBLIC:
                info["public_methods"].append({
                    "name": c.spelling,
                    "signature": get_signature(c),
                    "is_constructor": True,
                    "doc": clean_comment(c.raw_comment),
                })
        elif c.kind == CursorKind.DESTRUCTOR:
            if c.access_specifier == AccessSpecifier.PUBLIC:
                info["public_methods"].append({
                    "name": c.spelling,
                    "signature": f"~{cursor.spelling}()",
                    "is_destructor": True,
                    "is_virtual": c.is_virtual_method(),
                    "doc": clean_comment(c.raw_comment),
                })
        elif c.kind == CursorKind.FIELD_DECL:
            if (c.access_specifier == AccessSpecifier.PUBLIC
                    and not is_internal(c.spelling)):
                info["public_fields"].append({
                    "name": c.spelling,
                    "type": c.type.spelling,
                    "doc": clean_comment(c.raw_comment),
                })
        elif c.kind in (CursorKind.CLASS_DECL,
                        CursorKind.STRUCT_DECL,
                        CursorKind.ENUM_DECL,
                        CursorKind.TYPEDEF_DECL,
                        CursorKind.TYPE_ALIAS_DECL):
            if c.spelling and not is_internal(c.spelling):
                info["nested_types"].append({
                    "name": c.spelling,
                    "kind": str(c.kind).split(".")[-1].lower(),
                })
    return info


def visit(cursor, main_file_resolved: Path, out: dict, skip_filter: bool) -> None:
    for child in cursor.get_children():
        if not child.location.file:
            continue
        try:
            child_file = Path(child.location.file.name).resolve()
        except (OSError, ValueError):
            continue

        if child.kind == CursorKind.NAMESPACE:
            visit(child, main_file_resolved, out, skip_filter)
            continue

        if child_file != main_file_resolved:
            continue

        name = child.spelling
        if not skip_filter and is_internal(name):
            continue

        if child.kind in (CursorKind.CLASS_DECL,
                          CursorKind.STRUCT_DECL,
                          CursorKind.CLASS_TEMPLATE):
            if child.is_definition() and name:
                out["classes"].append(extract_class(child))
        elif child.kind == CursorKind.FUNCTION_DECL:
            if name:
                out["functions"].append({
                    "name": name,
                    "qualified_name": qualified(child),
                    "signature": get_signature(child),
                    "file": str(child_file),
                    "line": child.location.line,
                    "doc": clean_comment(child.raw_comment),
                })
        elif child.kind == CursorKind.ENUM_DECL:
            if name:
                values = []
                for v in child.get_children():
                    if v.kind == CursorKind.ENUM_CONSTANT_DECL:
                        values.append({
                            "name": v.spelling,
                            "value": v.enum_value,
                        })
                out["enums"].append({
                    "name": name,
                    "qualified_name": qualified(child),
                    "file": str(child_file),
                    "line": child.location.line,
                    "values": values,
                    "doc": clean_comment(child.raw_comment),
                })
        elif child.kind in (CursorKind.TYPEDEF_DECL,
                            CursorKind.TYPE_ALIAS_DECL):
            if name:
                out["typedefs"].append({
                    "name": name,
                    "qualified_name": qualified(child),
                    "underlying": child.underlying_typedef_type.spelling,
                    "file": str(child_file),
                    "line": child.location.line,
                })
        elif child.kind == CursorKind.VAR_DECL:
            # Catch `extern const` API constants etc.
            if name and (child.storage_class == ci.StorageClass.EXTERN
                         or child.type.is_const_qualified()):
                out["variables"].append({
                    "name": name,
                    "qualified_name": qualified(child),
                    "type": child.type.spelling,
                    "file": str(child_file),
                    "line": child.location.line,
                })


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)
    setup_libclang(cfg.get("libclang_path"))

    src_root = Path(cfg["src_root"])
    if not src_root.exists():
        print(f"Error: src_root not found: {src_root}", file=sys.stderr)
        return 1

    output_dir = Path(cfg["output_dir"]) / "symbols"
    output_dir.mkdir(parents=True, exist_ok=True)

    compile_db = None
    if cfg.get("compile_commands"):
        cc_path = Path(cfg["compile_commands"])
        if cc_path.exists():
            compile_db = load_compile_commands(cc_path)
            print(f"Loaded compile_commands.json: {len(compile_db)} entries")

    index = ci.Index.create()
    empty_bucket = lambda: {  # noqa: E731
        "classes": [], "functions": [], "enums": [],
        "typedefs": [], "variables": [], "file_count": 0,
    }
    by_module: dict = defaultdict(empty_bucket)

    headers = list(iter_cpp_files(src_root,
                                  set(cfg["exclude_dirs"]),
                                  DEFAULT_HEADER_EXTS))
    print(f"Parsing {len(headers)} header file(s)...")

    for i, h in enumerate(headers, 1):
        module = resolve_module(h, src_root, cfg["module_depth"])
        if not module:
            continue
        if args.verbose or i % 100 == 0:
            print(f"  [{i}/{len(headers)}] {h}")

        file_args = build_compile_args(cfg, h, compile_db)
        try:
            tu = index.parse(
                str(h),
                args=file_args,
                options=(TranslationUnit.PARSE_SKIP_FUNCTION_BODIES
                         | TranslationUnit.PARSE_INCOMPLETE),
            )
        except ci.TranslationUnitLoadError as e:
            if args.verbose:
                print(f"  [WARN] {h}: {e}", file=sys.stderr)
            continue

        out = {"classes": [], "functions": [], "enums": [],
               "typedefs": [], "variables": []}
        visit(tu.cursor, h.resolve(), out, args.no_filter)

        bucket = by_module[module]
        for k in out:
            bucket[k].extend(out[k])
        bucket["file_count"] += 1

    summary: dict = {}
    for module, data in sorted(by_module.items()):
        out_path = output_dir / f"{module.replace('/', '__')}.json"
        payload = {"module": module, **data}
        out_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        summary[module] = {
            "files": data["file_count"],
            "classes": len(data["classes"]),
            "functions": len(data["functions"]),
            "enums": len(data["enums"]),
            "typedefs": len(data["typedefs"]),
            "variables": len(data["variables"]),
        }
        print(f"  {module}: {summary[module]}")

    (output_dir / "_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nDone. {len(by_module)} module(s) -> {output_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())

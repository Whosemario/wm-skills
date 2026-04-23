#!/usr/bin/env python3
"""Step 2: Build module-level include dependency graph.

Scans `#include "..."` directives across the source tree, aggregates to the
module level, and emits:
  - <output_dir>/deps.mermaid.md    -- Mermaid graph
  - <output_dir>/deps.json          -- Edge list with example includes
  - <output_dir>/violations.md      -- Layering rule breaches (if any)

Usage:
    python build_dep_graph.py --config codemap.json [-v]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

from common import (
    DEFAULT_HEADER_EXTS,
    DEFAULT_SOURCE_EXTS,
    iter_cpp_files,
    load_config,
    resolve_module,
)


# Match:  #include "..."   (we deliberately ignore <system> includes)
INCLUDE_RE = re.compile(r'^[ \t]*#[ \t]*include[ \t]*"([^"]+)"', re.MULTILINE)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--config", type=Path, default=Path("codemap.json"))
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args()


def build_header_index(src_root: Path, exclude_dirs: set) -> dict:
    """Return suffix -> [header paths].

    Every suffix of every header's path relative to src_root is indexed, so
    we can resolve `#include "render/rhi/IRHIDevice.h"` whether the project
    uses a flat or hierarchical include style.
    """
    index: dict = defaultdict(list)
    src_root_resolved = src_root.resolve()

    for root, dirs, files in os.walk(src_root):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for f in files:
            if not f.endswith(DEFAULT_HEADER_EXTS):
                continue
            full = (Path(root) / f).resolve()
            try:
                rel = full.relative_to(src_root_resolved)
            except ValueError:
                continue
            parts = rel.parts
            # Every trailing suffix becomes a lookup key.
            for i in range(len(parts)):
                suffix = "/".join(parts[i:])
                index[suffix].append(full)
    return index


def resolve_include(
    include_str: str,
    index: dict,
    current_file: Path,
    src_root: Path,
) -> Optional[Path]:
    """Resolve a quoted include to an actual file path, or None."""
    normalized = include_str.replace("\\", "/")
    src_root_resolved = src_root.resolve()

    # 1) Relative to the current file's directory (most common).
    candidate = (current_file.parent / normalized).resolve()
    if candidate.is_file():
        return candidate

    # 2) Relative to src_root (project-style includes).
    candidate = (src_root / normalized).resolve()
    if candidate.is_file():
        return candidate

    # 3) Suffix match in the header index.
    hits = index.get(normalized) or index.get(Path(normalized).name)
    if not hits:
        return None
    if len(hits) == 1:
        return hits[0]

    # Multiple matches: prefer the one in the current file's module.
    try:
        cur_rel = current_file.resolve().relative_to(src_root_resolved)
        cur_top = cur_rel.parts[0] if cur_rel.parts else ""
    except ValueError:
        cur_top = ""
    for h in hits:
        try:
            rel = h.relative_to(src_root_resolved)
            if rel.parts and rel.parts[0] == cur_top:
                return h
        except ValueError:
            continue
    return hits[0]


def find_includes(file_path: Path) -> list:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return INCLUDE_RE.findall(f.read())
    except OSError:
        return []


def check_violations(edges: dict, layering_rules: dict) -> list:
    """A module listed in layering_rules may only depend on rules[module].

    Modules absent from rules have no restriction.
    """
    violations: list = []
    for (a, b), details in edges.items():
        if a not in layering_rules:
            continue
        allowed = set(layering_rules[a])
        if b in allowed:
            continue
        violations.append({
            "from": a,
            "to": b,
            "allowed": sorted(allowed),
            "count": details["count"],
            "examples": details["examples"][:5],
        })
    return violations


def _node_id(name: str) -> str:
    # Mermaid node IDs need to be identifier-safe.
    return name.replace("/", "__").replace("-", "_").replace(".", "_")


def render_mermaid(edges: dict, modules: set) -> str:
    lines = ["```mermaid", "graph LR"]
    for m in sorted(modules):
        lines.append(f'    {_node_id(m)}["{m}"]')
    for (a, b), details in sorted(edges.items()):
        # Light edge labelling with include counts.
        lines.append(
            f'    {_node_id(a)} -->|{details["count"]}| {_node_id(b)}'
        )
    lines.append("```")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)

    src_root = Path(cfg["src_root"])
    if not src_root.exists():
        print(f"Error: src_root not found: {src_root}", file=sys.stderr)
        return 1

    output_dir = Path(cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    exclude_dirs = set(cfg["exclude_dirs"])
    module_depth = cfg["module_depth"]

    print("Indexing headers...")
    header_index = build_header_index(src_root, exclude_dirs)
    unique_headers = {p for hits in header_index.values() for p in hits}
    print(f"  indexed {len(unique_headers)} unique header(s)")

    all_files = list(iter_cpp_files(
        src_root, exclude_dirs,
        DEFAULT_HEADER_EXTS + DEFAULT_SOURCE_EXTS,
    ))
    print(f"Scanning {len(all_files)} file(s) for includes...")

    edges: dict = defaultdict(lambda: {"count": 0, "examples": []})
    modules: set = set()
    unresolved: dict = defaultdict(int)
    src_root_resolved = src_root.resolve()

    for i, f in enumerate(all_files, 1):
        if args.verbose and i % 500 == 0:
            print(f"  [{i}/{len(all_files)}]")
        from_module = resolve_module(f, src_root, module_depth)
        if not from_module:
            continue
        modules.add(from_module)

        for inc in find_includes(f):
            target = resolve_include(inc, header_index, f, src_root)
            if target is None:
                unresolved[inc] += 1
                continue
            to_module = resolve_module(target, src_root, module_depth)
            if not to_module or to_module == from_module:
                continue
            modules.add(to_module)

            edge = edges[(from_module, to_module)]
            edge["count"] += 1
            if len(edge["examples"]) < 10:
                try:
                    rel = f.resolve().relative_to(src_root_resolved)
                except ValueError:
                    rel = f
                edge["examples"].append({
                    "file": str(rel),
                    "include": inc,
                })

    # --- write outputs ---
    mermaid = render_mermaid(edges, modules)
    (output_dir / "deps.mermaid.md").write_text(
        "# Module Dependency Graph\n\n"
        f"_Auto-generated. {len(modules)} modules, {len(edges)} edges._\n\n"
        + mermaid + "\n",
        encoding="utf-8",
    )

    edges_json = {
        f"{a} -> {b}": {"count": d["count"], "examples": d["examples"]}
        for (a, b), d in sorted(edges.items())
    }
    (output_dir / "deps.json").write_text(
        json.dumps(
            {"modules": sorted(modules), "edges": edges_json},
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    violations = check_violations(edges, cfg.get("layering_rules", {}))
    if violations:
        lines = ["# Layering Violations",
                 "",
                 f"_{len(violations)} violation(s) detected._",
                 ""]
        for v in violations:
            lines.append(
                f"## `{v['from']}` &rarr; `{v['to']}` "
                f"({v['count']} include(s))"
            )
            lines.append("")
            lines.append(
                f"Allowed dependencies for `{v['from']}`: "
                + (", ".join(f"`{x}`" for x in v["allowed"]) or "_none_")
            )
            lines.append("")
            lines.append("Examples:")
            for ex in v["examples"]:
                lines.append(
                    f'- `{ex["file"]}`: `#include "{ex["include"]}"`'
                )
            lines.append("")
        (output_dir / "violations.md").write_text(
            "\n".join(lines), encoding="utf-8"
        )
        print(f"\n[WARN] {len(violations)} layering violation(s) "
              f"-> {output_dir}/violations.md")
    else:
        vpath = output_dir / "violations.md"
        if vpath.exists():
            vpath.unlink()
        if cfg.get("layering_rules"):
            print("\n[OK] No layering violations.")

    if unresolved and args.verbose:
        print("\nTop unresolved includes:")
        for inc, cnt in sorted(unresolved.items(), key=lambda x: -x[1])[:20]:
            print(f"  {cnt:4d}  {inc}")

    print(f"\nDone. {len(modules)} module(s), {len(edges)} edge(s) "
          f"-> {output_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Render Jinja templates + content JSON into a static site directory."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


def render_site(template_dir: Path, content_path: Path, out_dir: Path) -> dict[str, Any]:
    if not template_dir.is_dir():
        raise SystemExit(f"error: template dir {template_dir} not found")
    if not content_path.is_file():
        raise SystemExit(f"error: content file {content_path} not found")

    content = json.loads(content_path.read_text(encoding="utf-8"))
    if not isinstance(content, dict):
        raise SystemExit("error: content JSON must be an object at the top level")
    site_globals = content.get("site", {})
    pages = content.get("pages", [])
    if not isinstance(pages, list):
        raise SystemExit("error: content.pages must be a list")

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(("html", "htm", "xml")),
        keep_trailing_newline=True,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_root_resolved = out_dir.resolve()
    rendered = 0
    for page in pages:
        if not isinstance(page, dict):
            continue
        template_name = page.get("template")
        out_relative = page.get("out")
        if not template_name or not out_relative:
            continue
        # Reject absolute paths and any traversal that escapes out_dir.
        out_relative_str = str(out_relative)
        candidate = Path(out_relative_str)
        if candidate.is_absolute() or candidate.drive:
            raise SystemExit(
                f"error: page.out must be relative (got {out_relative_str!r})"
            )
        out_path = (out_dir / candidate).resolve()
        try:
            out_path.relative_to(out_root_resolved)
        except ValueError as exc:
            raise SystemExit(
                f"error: page.out {out_relative_str!r} escapes the output dir"
            ) from exc
        template = env.get_template(template_name)
        ctx: dict[str, Any] = {"site": site_globals}
        page_data = page.get("data") or {}
        if isinstance(page_data, dict):
            ctx.update(page_data)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(template.render(**ctx), encoding="utf-8")
        rendered += 1

    static_src = template_dir / "static"
    static_count = 0
    if static_src.is_dir():
        static_dst = out_dir / "static"
        if static_dst.exists():
            shutil.rmtree(static_dst)
        shutil.copytree(static_src, static_dst)
        static_count = sum(1 for _ in static_dst.rglob("*") if _.is_file())

    return {
        "rendered_pages": rendered,
        "static_files_copied": static_count,
        "out_dir": str(out_dir),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a static site from templates + content.")
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--content", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary = render_site(args.template, args.content, args.out)
    sys.stdout.write(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

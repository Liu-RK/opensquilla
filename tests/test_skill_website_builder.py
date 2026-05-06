"""website-builder skill — load + generate produces expected files."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from opensquilla.skills.eligibility import EligibilityContext, check_eligibility
from opensquilla.skills.loader import SkillLoader

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "src" / "opensquilla" / "skills" / "bundled"
SCRIPTS = BUNDLED / "website-builder" / "scripts"


def _spec() -> object:
    return SkillLoader(bundled_dir=BUNDLED).get_by_name("website-builder")


def test_skill_loads() -> None:
    spec = _spec()
    assert spec is not None
    assert spec.name == "website-builder"


def test_eligibility_with_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "opensquilla.skills.eligibility.shutil.which",
        lambda name: "/usr/bin/python3" if name in {"python", "python3"} else None,
    )
    spec = _spec()
    assert spec is not None
    assert check_eligibility(spec, EligibilityContext.auto())


def test_generate_renders_pages_and_static(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import generate  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    template_dir = tmp_path / "tpl"
    template_dir.mkdir()
    (template_dir / "base.html.j2").write_text(
        """<!doctype html><html><head><title>{{ site.title }}</title></head>
<body>{% block main %}{% endblock %}</body></html>""",
        encoding="utf-8",
    )
    (template_dir / "index.html.j2").write_text(
        """{% extends 'base.html.j2' %}
{% block main %}<h1>{{ hero }}</h1>{% endblock %}""",
        encoding="utf-8",
    )
    static_dir = template_dir / "static"
    static_dir.mkdir()
    (static_dir / "styles.css").write_text("body { color: black; }", encoding="utf-8")

    content_path = tmp_path / "content.json"
    content_path.write_text(
        json.dumps(
            {
                "site": {"title": "Test Site"},
                "pages": [
                    {
                        "template": "index.html.j2",
                        "out": "index.html",
                        "data": {"hero": "Hello world"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "site"
    summary = generate.render_site(template_dir, content_path, out_dir)
    assert summary["rendered_pages"] == 1
    assert summary["static_files_copied"] == 1

    rendered = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "<title>Test Site</title>" in rendered
    assert "Hello world" in rendered

    css = (out_dir / "static" / "styles.css").read_text(encoding="utf-8")
    assert "color: black" in css


def test_generate_rejects_path_traversal(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import generate  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    template_dir = tmp_path / "tpl"
    template_dir.mkdir()
    (template_dir / "page.html.j2").write_text("hi", encoding="utf-8")

    for hostile in ("../escape.html", "../../escape.html", "a/../../escape.html"):
        content_path = tmp_path / "content.json"
        content_path.write_text(
            json.dumps(
                {
                    "site": {"title": "x"},
                    "pages": [{"template": "page.html.j2", "out": hostile}],
                }
            ),
            encoding="utf-8",
        )
        out_dir = tmp_path / "site"
        with pytest.raises(SystemExit, match="escapes the output dir"):
            generate.render_site(template_dir, content_path, out_dir)


def test_generate_rejects_absolute_out_path(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import generate  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    template_dir = tmp_path / "tpl"
    template_dir.mkdir()
    (template_dir / "page.html.j2").write_text("hi", encoding="utf-8")

    content_path = tmp_path / "content.json"
    # Absolute path on Windows ("C:/...") and POSIX ("/etc/...") both rejected.
    abs_target = "C:/Windows/System32/foo.html" if sys.platform == "win32" else "/etc/foo.html"
    content_path.write_text(
        json.dumps(
            {
                "site": {"title": "x"},
                "pages": [{"template": "page.html.j2", "out": abs_target}],
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "site"
    with pytest.raises(SystemExit, match="must be relative"):
        generate.render_site(template_dir, content_path, out_dir)


def test_generate_handles_nested_out_paths(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import generate  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    template_dir = tmp_path / "tpl"
    template_dir.mkdir()
    (template_dir / "page.html.j2").write_text(
        "<p>{{ name }}</p>",
        encoding="utf-8",
    )
    content_path = tmp_path / "content.json"
    content_path.write_text(
        json.dumps(
            {
                "site": {"title": "x"},
                "pages": [
                    {
                        "template": "page.html.j2",
                        "out": "about/index.html",
                        "data": {"name": "A"},
                    },
                    {
                        "template": "page.html.j2",
                        "out": "blog/post-1/index.html",
                        "data": {"name": "B"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "site"
    summary = generate.render_site(template_dir, content_path, out_dir)
    assert summary["rendered_pages"] == 2
    assert (out_dir / "about" / "index.html").is_file()
    assert (out_dir / "blog" / "post-1" / "index.html").is_file()

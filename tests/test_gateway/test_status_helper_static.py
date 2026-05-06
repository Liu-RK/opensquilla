from pathlib import Path

COMPONENTS_JS = Path("src/opensquilla/gateway/static/js/components.js")
SESSIONS_JS = Path("src/opensquilla/gateway/static/js/views/sessions.js")
OVERVIEW_JS = Path("src/opensquilla/gateway/static/js/views/overview.js")


def test_components_js_defines_session_status_helpers() -> None:
    source = COMPONENTS_JS.read_text(encoding="utf-8")

    # Function names exposed on window.UI.
    assert "sessionStatusClass" in source
    assert "sessionStatusChip" in source
    assert "sessionStatusLabel" in source

    # Every SessionStatus key must appear in the dot+chip lookup tables.
    for status in ("running", "done", "failed", "killed", "timeout"):
        assert f"{status}:" in source, f"missing status key '{status}' in components.js"

    # Default-branch literal — covers the unknown-input fall-through.
    # The new dot vocabulary uses 'off' for muted/unknown.
    assert "|| 'off'" in source

    # Human-readable labels used for tooltips / aria-labels.
    for label in ("Running", "Completed", "Failed", "Aborted by operator", "Timed out"):
        assert label in source, f"missing tooltip label '{label}' in components.js"


def test_sessions_view_uses_status_helper() -> None:
    source = SESSIONS_JS.read_text(encoding="utf-8")

    assert "UI.sessionStatusClass(" in source
    assert "UI.sessionStatusChip(" in source
    assert "UI.sessionStatusLabel(" in source

    # Legacy 3-bucket ternary fragment must be gone.
    assert "=== 'running' || s.status === 'active'" not in source


def test_overview_view_uses_status_helper() -> None:
    source = OVERVIEW_JS.read_text(encoding="utf-8")

    assert "UI.sessionStatusClass(" in source

    # Legacy 3-bucket ternary fragment must be gone.
    assert "? 'is-on'" not in source

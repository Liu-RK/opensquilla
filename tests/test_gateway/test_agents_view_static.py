from pathlib import Path

AGENTS_JS = Path("src/opensquilla/gateway/static/js/views/agents.js")
AGENTS_CSS = Path("src/opensquilla/gateway/static/css/views/agents.css")


def test_agents_view_has_create_and_delete_controls() -> None:
    source = AGENTS_JS.read_text(encoding="utf-8")
    css = AGENTS_CSS.read_text(encoding="utf-8")

    assert 'id="agent-add-form"' in source
    assert "_rpc.call('agents.create'" in source
    assert "_rpc.call('agents.delete'" in source
    assert "data-delete-agent" in source
    assert "a.isBuiltin" in source
    assert ".ag-create" in css

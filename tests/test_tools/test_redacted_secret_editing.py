from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path

import pytest

from opensquilla.engine.types import ToolCall
from opensquilla.safety.secret_redaction import redact_secret_text
from opensquilla.tools import get_default_registry
from opensquilla.tools.builtin import filesystem
from opensquilla.tools.builtin import patch as patch_tool
from opensquilla.tools.dispatch import build_tool_handler
from opensquilla.tools.types import RetryableToolInputError, ToolContext, current_tool_context


def _original_async(fn: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__  # type: ignore[attr-defined]
    return fn


@pytest.fixture
def workspace_context(tmp_path: Path) -> Iterator[Path]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    token = current_tool_context.set(
        ToolContext(
            is_owner=True,
            workspace_dir=str(workspace),
            file_edit_requires_fresh_read=True,
            allowed_tools={"read_file", "read_source"},
            surfaced_tools={"read_file", "read_source"},
        )
    )
    try:
        yield workspace
    finally:
        current_tool_context.reset(token)


@pytest.mark.asyncio
async def test_read_file_redacts_quoted_json_secret_before_line_numbering(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "settings.json"
    target.parent.mkdir()
    target.write_text('{"password":"json_password","name":"visible"}\n', encoding="utf-8")
    ctx = current_tool_context.get()
    assert ctx is not None
    handler = build_tool_handler(get_default_registry(), ctx)

    result = await handler(
        ToolCall(
            tool_use_id="read-file-secret",
            tool_name="read_file",
            arguments={"path": str(target)},
        )
    )
    output = result.content

    assert result.is_error is False
    assert "json_password" not in output
    assert '1\t{"password":"[REDACTED]","name":"visible"}' in output


@pytest.mark.asyncio
async def test_read_source_redacts_quoted_json_secret_before_receipt_encoding(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "settings.json"
    target.parent.mkdir()
    target.write_text('{"password":"json_password","name":"visible"}\n', encoding="utf-8")
    ctx = current_tool_context.get()
    assert ctx is not None
    handler = build_tool_handler(get_default_registry(), ctx)

    result = await handler(
        ToolCall(
            tool_use_id="read-source-secret",
            tool_name="read_source",
            arguments={"path": str(target)},
        )
    )
    receipt = json.loads(result.content)

    assert result.is_error is False
    assert "json_password" not in str(receipt)
    assert receipt["lines"][0]["text"] == (
        '{"password":"[REDACTED]","name":"visible"}'
    )


@pytest.mark.asyncio
async def test_edit_file_preserves_two_redacted_yaml_passwords(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "database.yml"
    target.parent.mkdir()
    original = (
        "development:\n"
        "  host: localhost\n"
        "  password: dev_password_123\n"
        "test:\n"
        "  host: localhost\n"
        "  password: test_password_456\n"
    )
    target.write_text(original, encoding="utf-8")
    masked = redact_secret_text(original)
    replacement = masked.replace("host: localhost", "host: prod-db.example.com")
    edit_file = _original_async(filesystem.edit_file)

    await filesystem.read_file(str(target))
    await edit_file(str(target), old_text=masked, new_text=replacement)

    assert target.read_text(encoding="utf-8") == (
        "development:\n"
        "  host: prod-db.example.com\n"
        "  password: dev_password_123\n"
        "test:\n"
        "  host: prod-db.example.com\n"
        "  password: test_password_456\n"
    )


@pytest.mark.asyncio
async def test_edit_file_can_replace_a_redacted_password_with_an_explicit_value(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "database.yml"
    target.parent.mkdir()
    target.write_text(
        "production:\n  username: app\n  password: old_password\n",
        encoding="utf-8",
    )
    edit_file = _original_async(filesystem.edit_file)

    await filesystem.read_file(str(target))
    await edit_file(
        str(target),
        old_text="  password:[REDACTED]\n",
        new_text="  password: rotated_password\n",
    )

    assert target.read_text(encoding="utf-8") == (
        "production:\n  username: app\n  password: rotated_password\n"
    )


@pytest.mark.asyncio
async def test_edit_file_reports_redacted_candidate_lines_without_leaking_secrets(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "database.yml"
    target.parent.mkdir()
    original = (
        "development:\n"
        "  password: dev_password_123\n"
        "production:\n"
        "  password: prod_password_456\n"
    )
    target.write_text(original, encoding="utf-8")
    edit_file = _original_async(filesystem.edit_file)

    await filesystem.read_file(str(target))
    with pytest.raises(RetryableToolInputError) as exc_info:
        await edit_file(
            str(target),
            old_text="  password:[REDACTED]\n",
            new_text="  password: rotated_password\n",
        )

    message = exc_info.value.user_message
    assert "matches 2 redacted locations" in message
    assert "Candidate lines: 2, 4." in message
    assert "dev_password_123" not in message
    assert "prod_password_456" not in message
    assert target.read_text(encoding="utf-8") == original


@pytest.mark.asyncio
async def test_edit_file_preserves_secret_when_same_line_metadata_changes(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "database.env"
    target.parent.mkdir()
    target.write_text("password=prod_password; host=localhost\n", encoding="utf-8")
    edit_file = _original_async(filesystem.edit_file)

    await filesystem.read_file(str(target))
    await edit_file(
        str(target),
        old_text="password=[REDACTED]; host=localhost\n",
        new_text="password=[REDACTED]; host=prod-db.example.com\n",
    )

    assert target.read_text(encoding="utf-8") == (
        "password=prod_password; host=prod-db.example.com\n"
    )


@pytest.mark.asyncio
async def test_write_file_preserves_redacted_json_password(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "settings.json"
    target.parent.mkdir()
    target.write_text(
        '{\n  "host": "localhost",\n  "password": "json_password"\n}\n',
        encoding="utf-8",
    )
    write_file = _original_async(filesystem.write_file)

    raw = await filesystem.read_file(str(target))
    masked = redact_secret_text(raw)
    assert "json_password" not in masked
    assert '"password": "[REDACTED]"' in masked
    await write_file(
        str(target),
        '{\n  "host": "prod-db.example.com",\n  "password": "[REDACTED]"\n}\n',
    )

    assert target.read_text(encoding="utf-8") == (
        '{\n  "host": "prod-db.example.com",\n  "password": "json_password"\n}\n'
    )


@pytest.mark.asyncio
async def test_write_file_preserves_one_secret_and_accepts_explicit_rotation(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "database.yml"
    target.parent.mkdir()
    target.write_text(
        "development:\n"
        "  password: dev_password_123\n"
        "test:\n"
        "  password: test_password_456\n",
        encoding="utf-8",
    )
    write_file = _original_async(filesystem.write_file)

    await filesystem.read_file(str(target))
    await write_file(
        str(target),
        "development:\n"
        "  password: rotated_dev_password\n"
        "test:\n"
        "  password:[REDACTED]\n",
    )

    assert target.read_text(encoding="utf-8") == (
        "development:\n"
        "  password: rotated_dev_password\n"
        "test:\n"
        "  password: test_password_456\n"
    )


@pytest.mark.asyncio
async def test_write_file_preserves_secret_when_same_line_metadata_changes(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "database.env"
    target.parent.mkdir()
    target.write_text("password=prod_password; host=localhost\n", encoding="utf-8")
    write_file = _original_async(filesystem.write_file)

    await filesystem.read_file(str(target))
    await write_file(str(target), "password=[REDACTED]; host=prod-db.example.com\n")

    assert target.read_text(encoding="utf-8") == (
        "password=prod_password; host=prod-db.example.com\n"
    )


@pytest.mark.asyncio
async def test_write_file_preserves_duplicate_fields_when_sections_are_reordered(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "database.yml"
    target.parent.mkdir()
    target.write_text(
        "development:\n  password: dev_password\n"
        "production:\n  password: prod_password\n",
        encoding="utf-8",
    )
    write_file = _original_async(filesystem.write_file)

    await filesystem.read_file(str(target))
    await write_file(
        str(target),
        "production:\n  password:[REDACTED]\n"
        "development:\n  password:[REDACTED]\n",
    )

    assert target.read_text(encoding="utf-8") == (
        "production:\n  password: prod_password\n"
        "development:\n  password: dev_password\n"
    )


@pytest.mark.asyncio
async def test_write_file_allows_mixed_rotation_and_preservation_on_one_line(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "database.env"
    target.parent.mkdir()
    target.write_text(
        "password=old_password; token=old_token\n",
        encoding="utf-8",
    )
    write_file = _original_async(filesystem.write_file)

    await filesystem.read_file(str(target))
    await write_file(
        str(target),
        "password=rotated_password; token=[REDACTED]\n",
    )

    assert target.read_text(encoding="utf-8") == (
        "password=rotated_password; token=old_token\n"
    )


@pytest.mark.asyncio
async def test_write_file_rejects_redacted_placeholder_in_a_new_file(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "new.yml"
    write_file = _original_async(filesystem.write_file)

    with pytest.raises(RetryableToolInputError, match="no existing secret"):
        await write_file(str(target), "password:[REDACTED]\n")

    assert not target.exists()


@pytest.mark.asyncio
async def test_apply_patch_uses_redacted_password_as_positioned_context(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "database.yml"
    target.parent.mkdir()
    target.write_text(
        "development:\n"
        "  host: localhost\n"
        "  password: dev_password_123\n"
        "  database: myapp_dev\n",
        encoding="utf-8",
    )
    apply_patch = _original_async(patch_tool.apply_patch)

    await apply_patch(
        """*** Begin Patch
*** Update File: config/database.yml
@@ -1,4 +1,4 @@
 development:
-  host: localhost
+  host: prod-db.example.com
   password:[REDACTED]
-  database: myapp_dev
+  database: myapp_prod
*** End Patch"""
    )

    assert target.read_text(encoding="utf-8") == (
        "development:\n"
        "  host: prod-db.example.com\n"
        "  password: dev_password_123\n"
        "  database: myapp_prod\n"
    )


@pytest.mark.asyncio
async def test_apply_patch_can_replace_a_redacted_password_with_an_explicit_value(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "database.yml"
    target.parent.mkdir()
    target.write_text("production:\n  password: old_password\n", encoding="utf-8")
    apply_patch = _original_async(patch_tool.apply_patch)

    await apply_patch(
        """*** Begin Patch
*** Update File: config/database.yml
@@ -2,1 +2,1 @@
-  password:[REDACTED]
+  password: rotated_password
*** End Patch"""
    )

    assert target.read_text(encoding="utf-8") == (
        "production:\n  password: rotated_password\n"
    )


@pytest.mark.asyncio
async def test_apply_patch_can_preserve_secret_on_a_changed_line(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "database.env"
    target.parent.mkdir()
    target.write_text("password=prod_password; host=localhost\n", encoding="utf-8")
    apply_patch = _original_async(patch_tool.apply_patch)

    await apply_patch(
        """*** Begin Patch
*** Update File: config/database.env
@@ -1,1 +1,1 @@
-password=[REDACTED]; host=localhost
+password=[REDACTED]; host=prod-db.example.com
*** End Patch"""
    )

    assert target.read_text(encoding="utf-8") == (
        "password=prod_password; host=prod-db.example.com\n"
    )


@pytest.mark.asyncio
async def test_apply_patch_redacts_secret_from_context_mismatch_error(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "database.yml"
    target.parent.mkdir()
    target.write_text("password: prod_password\n", encoding="utf-8")
    apply_patch = _original_async(patch_tool.apply_patch)

    with pytest.raises(RetryableToolInputError) as caught:
        await apply_patch(
            """*** Begin Patch
*** Update File: config/database.yml
@@ -1,1 +1,1 @@
-token:[REDACTED]
+token: rotated_token
*** End Patch"""
        )

    assert "prod_password" not in str(caught.value)
    assert "password:[REDACTED]" in str(caught.value)
    assert target.read_text(encoding="utf-8") == "password: prod_password\n"


@pytest.mark.asyncio
async def test_apply_patch_rejects_redacted_placeholder_without_an_old_value(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "new.yml"
    apply_patch = _original_async(patch_tool.apply_patch)

    with pytest.raises(RetryableToolInputError, match="no existing secret"):
        await apply_patch(
            """*** Begin Patch
*** Add File: config/new.yml
+password:[REDACTED]
*** End Patch"""
        )

    assert not target.exists()


@pytest.mark.asyncio
async def test_edit_source_preserves_redacted_password_at_its_line_range(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "database.yml"
    target.parent.mkdir()
    target.write_text(
        "production:\n  host: localhost\n  password: prod_password\n",
        encoding="utf-8",
    )
    edit_source = _original_async(filesystem.edit_source)
    revision = filesystem.source_revision_for_path(target)

    await edit_source(
        str(target),
        expected_revision=revision,
        edits=[
            {
                "start_line": 2,
                "end_line": 3,
                "replacement": "  host: prod-db.example.com\n  password:[REDACTED]\n",
            }
        ],
    )

    assert target.read_text(encoding="utf-8") == (
        "production:\n  host: prod-db.example.com\n  password: prod_password\n"
    )


@pytest.mark.asyncio
async def test_edit_source_preserves_secret_when_same_line_metadata_changes(
    workspace_context: Path,
) -> None:
    target = workspace_context / "config" / "database.env"
    target.parent.mkdir()
    target.write_text("password=prod_password; host=localhost\n", encoding="utf-8")
    edit_source = _original_async(filesystem.edit_source)
    revision = filesystem.source_revision_for_path(target)

    await edit_source(
        str(target),
        expected_revision=revision,
        edits=[
            {
                "start_line": 1,
                "end_line": 1,
                "replacement": "password=[REDACTED]; host=prod-db.example.com\n",
            }
        ],
    )

    assert target.read_text(encoding="utf-8") == (
        "password=prod_password; host=prod-db.example.com\n"
    )

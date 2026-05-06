"""Shared channel-plugin contract assertions.

Every shipped adapter's ``tests/test_channels/test_<name>_contract.py``
imports ``run_channel_contract`` and hands it the adapter module so the
shared invariants — capability tier, DM safety posture, error-class
taxonomy — are verified the same way for every channel.

The contract surface is intentionally narrow: only invariants that ALL
DM/group adapters honor live here. Per-adapter routing-key shapes,
mention parsing, and webhook-specific tests stay in the adapter's own
contract test file.
"""

from __future__ import annotations

from types import ModuleType

# ---------------------------------------------------------------------------
# Allowed values
# ---------------------------------------------------------------------------

PUBLIC_VENDOR_ADAPTERS: tuple[str, ...] = (
    "slack",
    "discord",
    "feishu",
    "dingtalk",
    "wecom",
    "qq",
    "msteams",
    "matrix",
    "telegram",
)

#: Capability tier values declared by adapters via ``CAPABILITY_TIER``.
ALLOWED_CAPABILITY_TIERS: frozenset[str] = frozenset(
    {
        "GREEN-shipping",
        "YELLOW-experimental",
        "RED-blocked",
    }
)

#: ``DM_SAFETY_TIERS`` values that are valid for DM/group adapters.
ALLOWED_DM_SAFETY_TIERS: frozenset[str] = frozenset({"safe", "confirm"})

#: Canonical retryable-error taxonomy. Every adapter declares this verbatim.
REQUIRED_RETRYABLE_ERROR_CLASSES: tuple[str, ...] = (
    "transport_transient",
    "rate_limited",
    "channel_degraded",
)

#: Canonical fatal-error taxonomy.
REQUIRED_FATAL_ERROR_CLASSES: tuple[str, ...] = (
    "auth_invalid",
    "payload_rejected",
    "target_missing",
    "contract_violation",
)


class ChannelCapabilities:
    """Capability tags an adapter may declare on its module.

    Tests can branch on these to skip irrelevant assertions (e.g. an adapter
    without webhook surface skips signature-verification checks).
    """

    STREAMING = "streaming"
    GROUP_CHAT = "group_chat"
    MENTIONS = "mentions"
    TYPING_INDICATOR = "typing_indicator"
    WEBHOOK = "webhook"
    WEBSOCKET = "websocket"


# ---------------------------------------------------------------------------
# Shared assertions
# ---------------------------------------------------------------------------


def assert_capability_tier(module: ModuleType) -> None:
    """``CAPABILITY_TIER`` must be one of the allowed values."""
    tier = getattr(module, "CAPABILITY_TIER", None)
    assert tier in ALLOWED_CAPABILITY_TIERS, (
        f"{module.__name__}.CAPABILITY_TIER={tier!r} must be one of "
        f"{sorted(ALLOWED_CAPABILITY_TIERS)}"
    )


def assert_dm_safety_tiers(module: ModuleType) -> None:
    """DM/group adapters must declare a non-empty safety-tier tuple without admin-only."""
    tiers = getattr(module, "DM_SAFETY_TIERS", None)
    assert isinstance(tiers, tuple), f"{module.__name__}.DM_SAFETY_TIERS must be a tuple"
    assert tiers, f"{module.__name__}.DM_SAFETY_TIERS must be non-empty"
    assert "admin-only" not in tiers, (
        f"{module.__name__}.DM_SAFETY_TIERS must not include 'admin-only' "
        "(DM/group adapters must not declare admin scope)."
    )
    for tier in tiers:
        assert tier in ALLOWED_DM_SAFETY_TIERS, (
            f"unknown safety tier {tier!r} in {module.__name__}.DM_SAFETY_TIERS"
        )


def assert_error_class_taxonomy(module: ModuleType) -> None:
    """Retryable + fatal error class tuples must match the canonical taxonomy."""
    retryable = getattr(module, "RETRYABLE_ERROR_CLASSES", None)
    fatal = getattr(module, "FATAL_ERROR_CLASSES", None)
    assert retryable == REQUIRED_RETRYABLE_ERROR_CLASSES, (
        f"{module.__name__}.RETRYABLE_ERROR_CLASSES diverges from canonical "
        f"taxonomy; got {retryable!r}"
    )
    assert fatal == REQUIRED_FATAL_ERROR_CLASSES, (
        f"{module.__name__}.FATAL_ERROR_CLASSES diverges from canonical taxonomy; got {fatal!r}"
    )


def run_channel_contract(module: ModuleType) -> None:
    """Run every shared invariant against an adapter module.

    Per-adapter contract tests call this once and then add adapter-specific
    assertions (routing-key shape, mention parsing) below the call site.
    """
    assert_capability_tier(module)
    assert_dm_safety_tiers(module)
    assert_error_class_taxonomy(module)


__all__ = [
    "ALLOWED_CAPABILITY_TIERS",
    "ALLOWED_DM_SAFETY_TIERS",
    "PUBLIC_VENDOR_ADAPTERS",
    "REQUIRED_FATAL_ERROR_CLASSES",
    "REQUIRED_RETRYABLE_ERROR_CLASSES",
    "ChannelCapabilities",
    "assert_capability_tier",
    "assert_dm_safety_tiers",
    "assert_error_class_taxonomy",
    "run_channel_contract",
]

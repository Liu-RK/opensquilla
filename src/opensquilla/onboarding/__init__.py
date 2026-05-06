"""Shared onboarding/configuration core used by CLI, RPC, and WebUI."""

from opensquilla.onboarding.channel_specs import (
    ChannelSetupField,
    ChannelSetupSpec,
    channel_catalog_payload,
    get_channel_setup_spec,
    list_channel_setup_specs,
)
from opensquilla.onboarding.image_generation_specs import (
    ImageGenerationProviderSetupField,
    ImageGenerationProviderSetupSpec,
    get_image_generation_provider_setup_spec,
    image_generation_provider_catalog_payload,
    list_image_generation_provider_setup_specs,
)
from opensquilla.onboarding.provider_specs import (
    ProviderSetupField,
    ProviderSetupSpec,
    get_provider_setup_spec,
    list_provider_setup_specs,
    provider_catalog_payload,
)
from opensquilla.onboarding.search_specs import (
    SearchProviderSetupField,
    SearchProviderSetupSpec,
    get_search_provider_setup_spec,
    list_search_provider_setup_specs,
    search_provider_catalog_payload,
)

__all__ = [
    "ChannelSetupField",
    "ChannelSetupSpec",
    "ImageGenerationProviderSetupField",
    "ImageGenerationProviderSetupSpec",
    "ProviderSetupField",
    "ProviderSetupSpec",
    "SearchProviderSetupField",
    "SearchProviderSetupSpec",
    "channel_catalog_payload",
    "get_channel_setup_spec",
    "get_image_generation_provider_setup_spec",
    "get_provider_setup_spec",
    "get_search_provider_setup_spec",
    "image_generation_provider_catalog_payload",
    "list_channel_setup_specs",
    "list_image_generation_provider_setup_specs",
    "list_provider_setup_specs",
    "list_search_provider_setup_specs",
    "provider_catalog_payload",
    "search_provider_catalog_payload",
]

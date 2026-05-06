"""Static-asset smoke tests for onboarding-aware WebUI views."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "src/opensquilla/gateway"
VIEWS = ROOT / "static/js/views"
TEMPLATE = ROOT / "templates/index.html"
APP = ROOT / "static/js/app.js"


def test_channels_view_calls_onboarding_rpc():
    txt = (VIEWS / "channels.js").read_text(encoding="utf-8")
    assert "onboarding.catalog" in txt
    assert "onboarding.channel.upsert" in txt
    assert "onboarding.channel.remove" in txt
    assert "onboarding.channel.enable" in txt
    assert "onboarding.channel.disable" in txt


def test_channels_view_uses_correct_toml_shape_copy():
    txt = (VIEWS / "channels.js").read_text(encoding="utf-8")
    # Old bad shape gone, new shape present.
    assert "[[channels]]" not in txt
    assert "channels.channels" in txt


def test_channels_view_shows_restart_required_notice():
    txt = (VIEWS / "channels.js").read_text(encoding="utf-8")
    assert "restart" in txt.lower()


def test_setup_view_loads_catalog_and_status():
    txt = (VIEWS / "setup.js").read_text(encoding="utf-8")
    assert "onboarding.catalog" in txt
    assert "onboarding.status" in txt
    assert "config.get" in txt
    assert "onboarding.provider.configure" in txt
    assert "onboarding.imageGeneration.configure" in txt
    assert "imageGenerationProviders" in txt
    assert "onboarding.memory_embedding.configure" in txt
    assert "Remote fallback API key" in txt
    assert "effectiveProvider" in txt
    assert "current.mode" in txt


def test_setup_view_is_loaded_and_registered():
    template = TEMPLATE.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    assert "static/js/views/setup.js" in template
    assert "SetupView.render" in app
    assert 'data-path="/setup"' in app


def test_setup_view_marks_unsupported_providers_disabled():
    txt = (VIEWS / "setup.js").read_text(encoding="utf-8")
    assert "runtimeSupported" in txt


def test_setup_view_treats_image_configure_as_capability_enable_action():
    txt = (VIEWS / "setup.js").read_text(encoding="utf-8")
    assert "field.default !== false" in txt
    assert "imageGenerationEnabled === false" in txt


def test_config_view_exposes_memory_tab_and_restart_notice():
    txt = (VIEWS / "config.js").read_text(encoding="utf-8")
    assert "label: 'Memory'" in txt
    assert "memory.embedding.provider" in txt
    assert "Restart required for memory changes" in txt


def test_example_config_does_not_advertise_local_embedding_model_override():
    txt = (ROOT.parents[2] / "opensquilla.toml.example").read_text(encoding="utf-8")
    local_section = txt.split("# [memory.embedding.local]", 1)[1].split(
        "# [memory.embedding.remote]",
        1,
    )[0]
    assert "model =" not in local_section
    assert "onnx_dir" in local_section

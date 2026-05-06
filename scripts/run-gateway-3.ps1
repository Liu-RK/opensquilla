# OpenSquilla gateway — third instance (loopback only, port 18794).
# State/workspace/logs/pidfile live under ~\.opensquilla_3 — fully isolated
# from gateway-1 (18790, ~\.opensquilla) and gateway-2 (18791, ~\.opensquilla_2).
# Used for ad-hoc testing of bundled skills (e.g. the pptx skill).
#
# Both env vars matter:
# - OPENSQUILLA_GATEWAY_CONFIG_PATH selects the config file (provider key etc.)
# - OPENSQUILLA_STATE_DIR isolates runtime state used by paths.default_opensquilla_home()
$env:OPENSQUILLA_STATE_DIR = "$HOME\.opensquilla_3"
$env:OPENSQUILLA_GATEWAY_CONFIG_PATH = "$HOME\.opensquilla_3\config.toml"
opensquilla gateway run --listen 127.0.0.1 --port 18794

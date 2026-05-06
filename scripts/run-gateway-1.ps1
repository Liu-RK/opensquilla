# OpenSquilla gateway — primary instance (loopback only, port 18790).
# State/workspace/logs/pidfile live under ~\.opensquilla
$env:OPENSQUILLA_STATE_DIR = "$HOME\.opensquilla"
opensquilla gateway run --listen 127.0.0.1 --port 18790

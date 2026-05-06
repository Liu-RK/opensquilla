# OpenSquilla gateway — second instance (LAN-accessible, port 18791).
# State/workspace/logs/pidfile live under ~\.opensquilla_2 — fully isolated
# from the primary instance. Bind 0.0.0.0 exposes the gateway on every
# interface, so anyone reachable on this LAN can hit the chat / sessions /
# config surfaces with this machine's provider credentials. Make sure the
# Windows firewall + your LAN are trusted before running this.
$env:OPENSQUILLA_STATE_DIR = "$HOME\.opensquilla_2"
opensquilla gateway run --listen 0.0.0.0 --port 18791

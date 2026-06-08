import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def _fetch_tunnels(api_port: int) -> list[dict]:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{api_port}/api/tunnels", timeout=1
        ) as response:
            data = json.loads(response.read().decode())
            return data.get("tunnels", [])
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return []


def _tunnel_is_online(public_url: str) -> bool:
    try:
        request = urllib.request.Request(
            f"{public_url.rstrip('/')}/prediction.html",
            method="HEAD",
            headers={"ngrok-skip-browser-warning": "1"},
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def get_active_ngrok_url(webapp_port: int = 8080) -> str | None:
    candidates: list[str] = []

    for api_port in (4041, 4040, 4042):
        for tunnel in _fetch_tunnels(api_port):
            if tunnel.get("proto") != "https":
                continue
            addr = tunnel.get("config", {}).get("addr", "")
            if f":{webapp_port}" not in addr and not addr.endswith(str(webapp_port)):
                continue
            public_url = tunnel.get("public_url")
            if public_url:
                candidates.append(public_url)

    for url in candidates:
        if _tunnel_is_online(url):
            return url

    return candidates[0] if candidates else None


def resolve_webapp_url(configured_url: str, webapp_port: int = 8080) -> str:
    active = get_active_ngrok_url(webapp_port)
    if active:
        if active.rstrip("/") != configured_url.rstrip("/"):
            logger.info("Используем актуальный ngrok URL: %s", active)
        return active.rstrip("/")
    return configured_url.rstrip("/")

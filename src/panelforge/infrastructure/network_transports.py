"""Direct transports for explicit LAN/Tailscale profiles, without global proxy changes."""
from inspect import signature
import urllib.request


def direct_http_opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({})).open


def _proxy_options(connect):
    # websockets 13/14 connect directly; 15 introduced automatic proxy discovery.
    return {"proxy": None} if "proxy" in signature(connect).parameters else {}


def direct_preview_connection(url):
    from websockets.asyncio.client import connect
    return connect(url, open_timeout=10, close_timeout=5, max_size=None, **_proxy_options(connect))


def direct_thermal_connection(url, timeout):
    from websockets.sync.client import connect
    return connect(url, open_timeout=timeout, close_timeout=1.0, **_proxy_options(connect))


def direct_dlss_connection(url):
    from websockets.sync.client import connect
    return connect(url, open_timeout=3, close_timeout=0.5, max_size=2**20, **_proxy_options(connect))

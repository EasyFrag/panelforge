"""Local subscription journal, optional Web Push adapter and loopback HTTP host."""
import base64
import json
import logging
import socket
from pathlib import Path
from functools import lru_cache
from io import BytesIO
from threading import Thread
from urllib.parse import urlsplit

from .storage.local import _atomic_write, _json_bytes, _read_json_object

LOG = logging.getLogger(__name__)


class LocalMobileStore:
    def __init__(self, workspace):
        self.path = Path(workspace) / "video_factory" / "mobile-subscriptions.json"

    def load(self):
        if not self.path.exists():
            return {}
        value = _read_json_object(self.path)
        if value.get("schema_version") != 1 or not isinstance(value.get("subscriptions"), dict):
            raise ValueError("Journal mobile invalide.")
        return value["subscriptions"]

    def save(self, subscriptions):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(self.path, _json_bytes(dict(schema_version=1, subscriptions=subscriptions)))


class WebPushSender:
    def __init__(self, workspace):
        self.available, self.public_key, self.warning = False, None, None
        self.path = Path(workspace) / "video_factory" / "mobile-vapid.pem"
        try:
            from pywebpush import webpush
            from py_vapid import Vapid
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                vapid = Vapid.from_file(str(self.path))
            else:
                vapid = Vapid()
                vapid.generate_keys()
                _atomic_write(self.path, vapid.private_pem())
            self.public_key = base64.urlsafe_b64encode(vapid.public_key.public_bytes(
                Encoding.X962, PublicFormat.UncompressedPoint)).decode().rstrip("=")
            self._send = webpush
            self.available = True
        except ImportError:
            self.warning = "Installer l’option Python mobile pour activer les notifications."
        except Exception:
            self.warning = "La clé des notifications est indisponible ; consulter le PC."

    @staticmethod
    def validate(subscription):
        url = urlsplit(subscription["endpoint"])
        if (url.scheme != "https" or url.hostname not in {
                "fcm.googleapis.com", "updates.push.services.mozilla.com", "push.services.mozilla.com"}
                or url.port not in {None, 443} or url.username or url.password or url.fragment):
            raise ValueError("Service de notification non pris en charge. Utilisez Chrome ou Firefox sur Android.")
        for key, size in (("p256dh", 65), ("auth", 16)):
            raw = subscription["keys"][key]
            try:
                value = base64.b64decode(raw + "=" * (-len(raw) % 4), altchars=b"-_", validate=True)
            except (ValueError, TypeError) as error:
                raise ValueError("Clé de notification invalide.") from error
            if len(value) != size:
                raise ValueError("Clé de notification invalide.")

    def send(self, subscription, message, origin):
        try:
            self.validate(subscription)
            self._send(subscription_info=subscription, data=json.dumps(message, ensure_ascii=False),
                       vapid_private_key=str(self.path), vapid_claims={"sub": origin},
                       ttl=300, timeout=5)
            return "sent"
        except Exception as error:
            response = getattr(error, "response", None)
            code = getattr(error, "status_code", None) or (response.status_code if response is not None else None)
            return "expired" if code in {404, 410} else "retry"


class LoopbackMobileServer:
    """Same application services, separate port exposing only the mobile surface."""
    def __init__(self, app, port):
        if not 1 <= port <= 65535:
            raise ValueError("Port mobile invalide.")
        self.app, self.port = app, port
        self.server = self.thread = self.socket = None

    def start(self):
        import uvicorn
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket = sock
            sock.bind(("127.0.0.1", self.port))
            sock.listen(128)
            # Uvicorn loggers are shared with the Lab: keep its startup URL and log policy.
            self.server = uvicorn.Server(uvicorn.Config(self.app, host="127.0.0.1", port=self.port,
                log_config=None, log_level=None, proxy_headers=True, forwarded_allow_ips="127.0.0.1",
                timeout_graceful_shutdown=8))
            self.thread = Thread(target=self.server.run, kwargs={"sockets": [sock]},
                                 name="factory-mobile-http", daemon=True)
            self.thread.start()
        except OSError:
            if self.socket:
                self.socket.close()
            LOG.exception("Accès mobile indisponible ; le Lab continue.")

    def stop(self):
        if self.server:
            self.server.should_exit = True
        if self.thread:
            self.thread.join(timeout=20)
        if self.socket:
            self.socket.close()


@lru_cache(maxsize=96)
def mobile_thumbnail(path, modified_ns, size):
    """Small phone thumbnails; originals remain unchanged."""
    from PIL import Image, ImageOps
    with Image.open(path) as source:
        preview = ImageOps.exif_transpose(source).convert("RGB")
        preview.thumbnail((384, 512))
        content = BytesIO()
        preview.save(content, format="JPEG", quality=78, optimize=True)
        return content.getvalue()

"""On-demand local ComfyUI lifecycle. Never controls the LLM or Bucket."""

import json
import os
from pathlib import Path
import subprocess
from threading import RLock
import time
import urllib.error
import urllib.parse
import urllib.request

from .storage.dlss_jobs import atomic_json


def windows_process_identity(pid):
    """Read executable and creation time using a process handle, without WMI or a shell."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    api.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    handle = api.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        code = wintypes.DWORD()
        if not api.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:
            return None
        times = [wintypes.FILETIME() for _ in range(4)]
        if not api.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            return None
        size = wintypes.DWORD(32768)
        path = ctypes.create_unicode_buffer(size.value)
        if not api.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
            return None
        return {"pid": pid, "created": (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
                "executable": str(Path(path.value).resolve()).casefold()}
    finally:
        api.CloseHandle(handle)


class LocalDlssRuntime:
    def __init__(self, *, root, base_url, journal, comfy, output_root=None, startup_timeout=180):
        self.root = Path(root).resolve()
        self.output_root = Path(output_root).resolve() if output_root is not None else None
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.path not in {"", "/"} or parsed.username or parsed.query or parsed.fragment:
            raise ValueError("DLSS doit utiliser une adresse HTTP locale dédiée.")
        self.base_url = base_url.rstrip("/")
        self.port = parsed.port or 80
        self.journal = journal
        self.comfy = comfy
        self.timeout = startup_timeout
        self.lock = RLock()
        self.process = None

    def _json(self, path, timeout=2):
        with urllib.request.urlopen(self.base_url + path, timeout=timeout) as response:
            return json.load(response)

    def ready(self):
        try:
            value = self._json("/system_stats")
            if not isinstance(value, dict) or "devices" not in value:
                raise ValueError("Le port DLSS est occupé par un service incompatible.")
            return True
        except urllib.error.HTTPError as error:
            raise ValueError("Le port DLSS répond mais n’est pas un ComfyUI compatible.") from error
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            return False

    def ownership(self):
        try:
            value = json.loads((self.journal.root / "runtime.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(value, dict) or type(value.get("pid")) is not int or value["pid"] <= 0:
            return None
        identity = windows_process_identity(value.get("pid", 0))
        expected = str((self.root / "python_embeded/python.exe").resolve()).casefold()
        if identity and identity == value.get("identity") and identity["executable"] == expected and value.get("url") == self.base_url:
            return identity
        return None

    def status(self):
        try:
            ready = self.ready()
            return {"state": "ready" if ready else "stopped", "owned": bool(self.ownership()), "url": self.base_url}
        except Exception as error:
            return {"state": "error", "owned": bool(self.ownership()), "url": self.base_url, "error": str(error)}

    def ensure_ready(self, required_nodes):
        with self.lock:
            if not self.ready():
                if os.name != "nt":
                    raise ValueError("Le démarrage DLSS nécessite Windows.")
                executable = self.root / "python_embeded/python.exe"
                script = self.root / "ComfyUI/main.py"
                ffmpeg, ffprobe = self.root / "tools/ffmpeg.exe", self.root / "tools/ffprobe.exe"
                if not all(p.is_file() for p in (executable, script, ffmpeg, ffprobe)):
                    raise ValueError("Installation Comfy DLSS incomplète : Python, ComfyUI, FFmpeg ou FFprobe absent.")
                if not self.ownership():
                    env = os.environ.copy()
                    env.update(DLSS_FFMPEG_PATH=str(ffmpeg), DLSS_FFPROBE_PATH=str(ffprobe))
                    command = [str(executable), "-s", str(script), "--windows-standalone-build", "--listen", "127.0.0.1", "--port", str(self.port)]
                    if self.output_root is not None:
                        command.extend(["--output-directory", str(self.output_root)])
                    with (self.journal.root / "comfy-local.log").open("ab") as log:
                        self.process = subprocess.Popen(
                            command,
                            cwd=self.root, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                    identity = windows_process_identity(self.process.pid)
                    if identity is None:
                        raise RuntimeError("Comfy local s’est arrêté au démarrage. Consulter son journal.")
                    atomic_json(self.journal.root / "runtime.json", {"pid": self.process.pid, "identity": identity, "url": self.base_url})
                deadline = time.monotonic() + self.timeout
                while not self.ready():
                    if self.process is not None and self.process.poll() is not None:
                        raise RuntimeError("Comfy local s’est arrêté au démarrage. Consulter son journal.")
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Comfy local ne répond pas encore. Réessaie après consultation du journal.")
                    time.sleep(1)
            for node in required_nodes:
                value = self._json("/object_info/" + urllib.parse.quote(node), timeout=15)
                if node not in value:
                    raise ValueError(f"Nœud manquant dans Comfy local : {node}.")

    def control(self, action):
        with self.lock:
            if action not in {"free", "stop", "restart"}:
                raise ValueError("Commande Comfy local inconnue.")
            snapshot = self.comfy.get_queue() if self.ready() else None
            if snapshot and (snapshot.running or snapshot.pending):
                raise ValueError("Comfy local a encore une tâche en cours ou en attente.")
            if action == "free":
                if snapshot:
                    self.comfy.free_vram()
                return
            identity = self.ownership()
            if not identity:
                raise ValueError("Cette instance n’a pas été démarrée par PanelForge ; ferme-la depuis son lanceur.")
            # Exact owned PID and its descendants only. The creation time/executable are checked above.
            try:
                subprocess.run(["taskkill.exe", "/PID", str(identity["pid"]), "/T", "/F"], check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW, timeout=20)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                raise RuntimeError("L’arrêt de Comfy local n’a pas pu être confirmé. Consulte son journal.") from error
            self.process = None
            if action == "restart":
                self.ensure_ready([])

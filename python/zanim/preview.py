"""Web-native development Preview for Python-authored Zanim scenes.

Preview no longer rasterizes frames in Python.  The server only exposes the
current Scene IR, timeline/debug metadata, the shared @zanim/web runtime assets,
and an explicit reload endpoint. Playback, seeking and inspection all
run in the browser through the same Web runtime used by static exports.
"""

from __future__ import annotations

import ipaddress
import json
import mimetypes
import re
import subprocess
import threading
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .geometry import Color
from .ir import _vector_document, scene_to_ir
from .source import get_preview_reload, reload_preview_scene
from .svg import load_svg
from .typst import Math, compile_typst_svg


def _is_loopback_host(host: str) -> bool:
    value = str(host).strip().lower()
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _repo_web_root() -> Path:
    return Path(__file__).resolve().parents[2] / "web"


def _packaged_web_root() -> Path:
    return Path(__file__).with_name("_web")


def _ensure_source_wasm() -> None:
    root = _repo_web_root()
    output = root / "dist" / "zanim_web_core.wasm"
    if output.is_file():
        return
    source = root.parent / "src" / "web_core.zig"
    if not source.is_file():
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "zig",
            "build-exe",
            str(source),
            "-target",
            "wasm32-freestanding",
            "-O",
            "ReleaseSmall",
            "-fno-entry",
            "-rdynamic",
            f"-femit-bin={output}",
        ],
        cwd=root.parent,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def _asset_path(relative: str) -> Path:
    relative = relative.lstrip("/")
    if ".." in Path(relative).parts:
        raise FileNotFoundError(relative)
    packaged = _packaged_web_root() / relative
    if packaged.is_file():
        return packaged
    source = _repo_web_root() / relative
    if relative == "dist/zanim_web_core.wasm" and not source.is_file():
        _ensure_source_wasm()
    if source.is_file():
        return source
    raise FileNotFoundError(relative)


class PreviewServer:
    """Tiny dev server for Scene IR + the shared browser runtime.

    No frame rasterization, frame cache, prefetch worker or RGB transport exists
    here.  The active browser is the Preview renderer.
    """

    def __init__(
        self,
        scene,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        allow_remote_reload: bool = False,
    ) -> None:
        self.scene = scene
        self.host = str(host)
        self.port = int(port)
        self.reload_allowed = _is_loopback_host(self.host) or bool(allow_remote_reload)
        self._state_lock = threading.RLock()
        self._reload_lock = threading.Lock()
        self._revision = 1
        self._ir: dict | None = None
        self._ir_error: dict | None = None
        self._media_assets: dict[str, Path] = {}
        self._compile_current_scene()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "ZanimWebPreview/1"

            def log_message(self, format: str, *args) -> None:
                return None

            def _bytes(self, payload: bytes, content_type: str, status=HTTPStatus.OK) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)

            def _json(self, value, status=HTTPStatus.OK) -> None:
                self._bytes(
                    json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                    "application/json; charset=utf-8",
                    status,
                )

            def _asset(self, relative: str) -> None:
                try:
                    path = _asset_path(relative)
                except (FileNotFoundError, subprocess.CalledProcessError) as exc:
                    self._json(
                        {"error": f"Web Preview asset unavailable: {exc}"}, HTTPStatus.NOT_FOUND
                    )
                    return
                payload = path.read_bytes()
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                if path.suffix == ".js":
                    content_type = "text/javascript; charset=utf-8"
                elif path.suffix == ".wasm":
                    content_type = "application/wasm"
                self._bytes(payload, content_type)

            def _file(self, path: Path) -> None:
                size = path.stat().st_size
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                start, end = 0, max(0, size - 1)
                status = HTTPStatus.OK
                raw_range = self.headers.get("Range")
                if raw_range:
                    match = re.fullmatch(r"bytes=(\d*)-(\d*)", raw_range.strip())
                    if match:
                        left, right = match.groups()
                        if left:
                            start = min(size, int(left))
                            end = min(end, int(right)) if right else end
                        elif right:
                            length = min(size, int(right))
                            start = size - length
                        if start > end or start >= size:
                            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                            self.send_header("Content-Range", f"bytes */{size}")
                            self.end_headers()
                            return
                        status = HTTPStatus.PARTIAL_CONTENT
                length = max(0, end - start + 1)
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "no-store")
                if status == HTTPStatus.PARTIAL_CONTENT:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.end_headers()
                with path.open("rb") as stream:
                    stream.seek(start)
                    remaining = length
                    while remaining:
                        chunk = stream.read(min(1024 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)

            def do_GET(self) -> None:
                try:
                    parsed = urlsplit(self.path)
                    if parsed.path == "/":
                        self._asset("preview/index.html")
                        return
                    if parsed.path == "/preview/main.js":
                        self._asset("preview/main.js")
                        return
                    if parsed.path.startswith("/web/"):
                        self._asset(parsed.path.removeprefix("/web/"))
                        return
                    if parsed.path.startswith("/api/media/"):
                        token = parsed.path.removeprefix("/api/media/")
                        with owner._state_lock:
                            path = owner._media_assets.get(token)
                        if path is None or not path.is_file():
                            self.send_error(HTTPStatus.NOT_FOUND)
                        else:
                            self._file(path)
                        return
                    if parsed.path == "/api/meta":
                        self._json(owner.metadata())
                        return
                    if parsed.path == "/api/ir":
                        ir, error = owner.current_ir()
                        if error is not None:
                            self._json(error, HTTPStatus.UNPROCESSABLE_ENTITY)
                        else:
                            self._json(ir)
                        return
                    self.send_error(HTTPStatus.NOT_FOUND)
                except BrokenPipeError:
                    pass
                except Exception as exc:
                    self._json(
                        {"error": str(exc), "traceback": traceback.format_exc()},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )

            def do_POST(self) -> None:
                parsed = urlsplit(self.path)
                if parsed.path == "/api/typst":
                    if not owner.reload_allowed:
                        self._json(
                            {
                                "ok": False,
                                "error": "Typst compilation is disabled for non-loopback Preview hosts",
                            },
                            HTTPStatus.FORBIDDEN,
                        )
                        return
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                        if length <= 0 or length > 1024 * 1024:
                            raise ValueError("Typst request body must be between 1 byte and 1 MiB")
                        payload = json.loads(self.rfile.read(length))
                        self._json(owner.compile_typst(payload))
                    except Exception as exc:
                        self._json(
                            {"ok": False, "error": str(exc), "traceback": traceback.format_exc()},
                            HTTPStatus.UNPROCESSABLE_ENTITY,
                        )
                    return
                if parsed.path != "/api/reload":
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                if not owner.reload_allowed:
                    self._json(
                        {
                            "ok": False,
                            "error": "source reload is disabled for non-loopback Preview hosts",
                        },
                        HTTPStatus.FORBIDDEN,
                    )
                    return
                params = parse_qs(parsed.query)
                try:
                    requested_time = float(params.get("t", ["0"])[0])
                    self._json(owner.reload_source(requested_time))
                except Exception as exc:
                    self._json(
                        {"ok": False, "error": str(exc), "traceback": traceback.format_exc()},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )

        self.httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = int(self.httpd.server_address[1])
        self._thread: threading.Thread | None = None

    def _compile_ir(self, scene) -> tuple[dict, dict[str, Path]]:
        media_assets: dict[str, Path] = {}
        media_keys: dict[Path, str] = {}

        def media_url(obj) -> str:
            path = Path(getattr(obj, "path", getattr(obj.source, "path", ""))).resolve()
            if not path.is_file():
                raise FileNotFoundError(path)
            token = media_keys.get(path)
            if token is None:
                token = f"m{len(media_assets) + 1}"
                media_keys[path] = token
                media_assets[token] = path
            return f"/api/media/{token}?r={self._revision}"

        ir = scene_to_ir(
            scene,
            sample_transform_functions=True,
            sample_dynamic_providers=True,
            sample_fps=scene.fps,
            include_debug=True,
            external_media_resolver=media_url,
        )
        ir.setdefault("meta", {})["preview_revision"] = self._revision
        return ir, media_assets

    def _compile_current_scene(self) -> None:
        with self._state_lock:
            try:
                self._ir, self._media_assets = self._compile_ir(self.scene)
                self._ir_error = None
            except Exception as exc:
                self._ir = None
                self._ir_error = {
                    "ok": False,
                    "error": str(exc),
                    "type": type(exc).__name__,
                    "traceback": traceback.format_exc(),
                }

    def current_ir(self) -> tuple[dict | None, dict | None]:
        with self._state_lock:
            return self._ir, self._ir_error

    @staticmethod
    def _web_color(value) -> Color:
        if isinstance(value, (list, tuple)) and len(value) in {3, 4}:
            channels = [int(x) for x in value]
            if len(channels) == 3:
                channels.append(255)
            return Color(*channels)
        text = str(value or "#eef2fa").strip()
        if re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", text):
            raw = text[1:]
            if len(raw) == 6:
                raw += "ff"
            return Color(*(int(raw[i : i + 2], 16) for i in range(0, 8, 2)))
        raise ValueError("Typst color must be #RRGGBB, #RRGGBBAA or RGBA channels")

    def compile_typst(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise TypeError("Typst request must be a JSON object")
        kind = str(payload.get("kind", "typst"))
        source = str(payload.get("source", ""))
        if not source:
            raise ValueError("Typst source must not be empty")
        if kind == "math":
            document = Math(
                source,
                font_size=float(payload.get("font_size", 36)),
                color=self._web_color(payload.get("color", "#eef2fa")),
            ).document
        elif kind == "typst":
            document = load_svg(compile_typst_svg(source))
        else:
            raise ValueError("Typst kind must be 'typst' or 'math'")
        return {"ok": True, "document": _vector_document(document)}

    def metadata(self) -> dict:
        with self._state_lock:
            return {
                "renderer": "web-ir",
                "revision": self._revision,
                "duration": float(self.scene.duration),
                "fps": int(self.scene.fps),
                "width": int(self.scene.width),
                "height": int(self.scene.height),
                "unit_size": float(self.scene.canvas.unit_size),
                "reload_available": bool(
                    self.reload_allowed and get_preview_reload(self.scene) is not None
                ),
                "ir_available": self._ir is not None,
                "ir_error": None if self._ir_error is None else self._ir_error["error"],
            }

    def reload_source(self, requested_time: float) -> dict:
        """Re-execute source and atomically replace the Scene IR on success."""
        with self._reload_lock:
            with self._state_lock:
                old_scene = self.scene
            new_scene = reload_preview_scene(old_scene)
            try:
                next_revision = self._revision + 1
                old_revision = self._revision
                self._revision = next_revision
                try:
                    new_ir, new_media_assets = self._compile_ir(new_scene)
                except BaseException:
                    self._revision = old_revision
                    raise
                preserved = max(0.0, min(float(requested_time), float(new_scene.duration)))
                with self._state_lock:
                    self.scene = new_scene
                    self._ir = new_ir
                    self._media_assets = new_media_assets
                    self._ir_error = None
                old_scene._close_media_sources()
                return {"ok": True, "time": preserved, "revision": next_revision}
            except BaseException:
                new_scene._close_media_sources()
                raise

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def serve_forever(self, *, open_browser: bool = True) -> None:
        if open_browser:
            threading.Timer(0.15, lambda: webbrowser.open(self.url)).start()
        print(f"Zanim web preview: {self.url}")
        try:
            self.httpd.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def start(self, *, open_browser: bool = True) -> "PreviewServer":
        if self._thread is not None:
            return self
        self._thread = threading.Thread(
            target=self.httpd.serve_forever,
            kwargs={"poll_interval": 0.2},
            name="zanim-web-preview-http",
            daemon=True,
        )
        self._thread.start()
        if open_browser:
            webbrowser.open(self.url)
        return self

    def close(self) -> None:
        if self._thread is not None:
            self.httpd.shutdown()
            if self._thread is not threading.current_thread():
                self._thread.join(timeout=1.0)
            self._thread = None
        self.httpd.server_close()
        with self._state_lock:
            self.scene._close_media_sources()


def preview_scene(scene, **kwargs) -> PreviewServer:
    """Launch the browser-native Scene IR Preview."""
    open_browser = bool(kwargs.pop("open_browser", True))
    block = bool(kwargs.pop("block", True))
    server = PreviewServer(scene, **kwargs)
    if block:
        server.serve_forever(open_browser=open_browser)
    else:
        server.start(open_browser=open_browser)
    return server

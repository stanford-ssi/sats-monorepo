"""Local HTTP server for SSIFT."""

import json
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import time_ns
from urllib.parse import urlparse

from plotly.offline import get_plotlyjs

from ssift.model import Dataset

_STATIC_DIRECTORY = Path(__file__).with_name("static")


def _handler(dataset: Dataset) -> type[SimpleHTTPRequestHandler]:
    telemetry_json = json.dumps(dataset.to_dict(), separators=(",", ":")).encode()
    plotly_javascript = get_plotlyjs().encode()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, directory=str(_STATIC_DIRECTORY), **kwargs)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/telemetry.json":
                self._send(telemetry_json, "application/json")
            elif path == "/plotly.min.js":
                self._send(plotly_javascript, "text/javascript")
            else:
                super().do_GET()

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def _send(self, content: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, _format: str, *_args) -> None:
            pass

    return Handler


def serve(
    dataset: Dataset,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    open_browser: bool = True,
) -> None:
    """Serve one dataset until interrupted."""
    server = ThreadingHTTPServer((host, port), _handler(dataset))
    url = f"http://{host}:{port}/?session={time_ns()}"
    print(f"SSIFT: {url}")
    if open_browser:
        webbrowser.open_new_tab(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

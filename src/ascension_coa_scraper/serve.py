"""Serve the repository so the viewer can read the datasets beside it.

The viewer is static, but it fetches JSON, so it needs an origin -- opening
``web/index.html`` from the filesystem leaves every fetch blocked. This is that origin
and nothing more: no framework, no reload, no build.

Three things it does that ``python -m http.server`` does not, each learned from this
project's own files:

* Threads. Single-threaded serving stalls on the 5.9 MB sprite sheet while the page is
  still asking for tree data.
* Types for the game's own extensions, so a probe for a model or texture comes back as
  a binary file rather than something the browser tries to interpret.
* Refuses dot-prefixed paths, which keeps .git off the wire when serving to a network.
"""

from __future__ import annotations

import functools
import json
import re
import socket
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from .bundle import ASSET_ROOT, BundleError, collect_class, collect_spell, write_zip
from .preview import (
    PreviewError,
    UnsupportedAsset,
    model_summary,
    safe_asset,
    texture_png,
)

__all__ = ["LOOPBACK", "ALL_INTERFACES", "Handler", "lan_addresses", "urls_for", "serve"]

LOOPBACK = "127.0.0.1"
ALL_INTERFACES = "0.0.0.0"

#: Extensions the game uses that the standard library has no opinion about. Declaring
#: them keeps a browser from sniffing a model file as something it might render.
EXTRA_TYPES = {
    ".m2": "application/octet-stream",
    ".mdx": "application/octet-stream",
    ".blp": "application/octet-stream",
    ".skin": "application/octet-stream",
    ".dbc": "application/octet-stream",
    ".mpq": "application/octet-stream",
    ".wdb": "application/octet-stream",
}


#: /_bundle/<realm>/<class>.zip and /_bundle/<realm>/<class>/<spell id>.zip
BUNDLE_RE = re.compile(
    r"^/_bundle/(?P<realm>[\w-]+)/(?P<cls>[\w-]+?)(?:/(?P<spell>\d+))?\.zip$"
)

#: /_texture/<asset path>.blp  -> PNG,  /_model/<asset path>.m2 -> JSON
TEXTURE_RE = re.compile(r"^/_texture/(?P<path>.+\.blp)$", re.IGNORECASE)
MODEL_RE = re.compile(r"^/_model/(?P<path>.+\.(?:m2|mdx))$", re.IGNORECASE)


class Handler(SimpleHTTPRequestHandler):
    """Static files, threaded, with the extra types and a dotfile guard.

    One dynamic route: /_bundle/... zips a talent's or a class's extracted assets so a
    reader can take them away. Everything else is a file on disk.
    """

    protocol_version = "HTTP/1.1"
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, **EXTRA_TYPES}

    @property
    def data_root(self) -> Path:
        return Path(self.directory) / "data"

    def do_GET(self) -> None:                       # noqa: N802 (stdlib naming)
        path = unquote(self.path.split("?")[0])

        bundle = BUNDLE_RE.match(path)
        if bundle:
            self.send_bundle(bundle)
            return

        texture = TEXTURE_RE.match(path)
        if texture:
            self.send_derived(
                lambda p: texture_png(p), texture["path"], "image/png")
            return

        model = MODEL_RE.match(path)
        if model:
            assets = self.data_root / ASSET_ROOT
            self.send_derived(
                lambda p: json.dumps(model_summary(p, assets=assets)).encode("utf-8"),
                model["path"], "application/json")
            return

        super().do_GET()

    def send_derived(self, convert, relative: str, content_type: str) -> None:
        """Convert one asset on the fly and send it.

        Derived from a file already on disk, so it is cacheable for as long as the
        page is open but never written anywhere.
        """
        try:
            payload = convert(safe_asset(self.data_root / ASSET_ROOT, relative))
        except UnsupportedAsset as exc:
            # Present but beyond the decoder: not the same answer as missing, and the
            # page says something different for each.
            self.send_error(415, "Unsupported Media Type", str(exc))
            return
        except PreviewError as exc:
            self.send_error(404, "Not Found", str(exc))
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "max-age=3600")
        self.end_headers()
        self.wfile.write(payload)

    def send_bundle(self, match: re.Match[str]) -> None:
        realm, cls, spell = match["realm"], match["cls"], match["spell"]
        try:
            bundle = (
                collect_spell(self.data_root, realm, cls, int(spell)) if spell
                else collect_class(self.data_root, realm, cls)
            )
            payload = write_zip(bundle)
        except BundleError as exc:
            self.send_error(404, "Not Found", str(exc))
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Content-Disposition", f'attachment; filename="{bundle.name}.zip"')
        # So the viewer can show what it just handed over without opening the archive.
        self.send_header("X-Bundle-Files", str(len(bundle)))
        self.send_header("X-Bundle-Missing", str(len(bundle.missing)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A002
        # One line per request would bury the address the user is waiting to see.
        return

    def send_head(self):
        if is_hidden(self.path):
            # Not merely tidiness: without this, serving to a network serves .git,
            # which carries every version of everything the repository ever held.
            self.send_error(404, "Not Found")
            return None
        return super().send_head()


def is_hidden(path: str) -> bool:
    """Whether any segment of a URL path is dot-prefixed."""
    return any(part.startswith(".") for part in path.split("?")[0].split("/") if part)


def lan_addresses() -> list[str]:
    """This host's non-loopback IPv4 addresses, best effort.

    Uses a UDP socket to a routable address to find the interface the kernel would
    actually use. No packet is sent -- connect() on UDP only sets the peer.
    """
    found: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))          # TEST-NET-1, never routed anywhere
            found.append(probe.getsockname()[0])
    except OSError:
        pass
    return [a for a in found if a and not a.startswith("127.")]


def urls_for(host: str, port: int) -> list[str]:
    """The addresses the viewer is reachable at, most useful first."""
    path = f":{port}/web/"
    if host in {ALL_INTERFACES, "::", ""}:
        return [f"http://{a}{path}" for a in lan_addresses()] + [f"http://localhost{path}"]
    if host in {LOOPBACK, "localhost"}:
        return [f"http://localhost{path}"]
    return [f"http://{host}{path}"]


def describe(host: str, port: int, root: Path) -> Iterator[str]:
    """What is being served, and to whom."""
    urls = urls_for(host, port)
    yield f"serving {root}"
    for url in urls:
        yield f"  {url}"
    if host not in {LOOPBACK, "localhost"}:
        yield ""
        yield "Reachable from the network. Everything in that directory is readable by"
        yield "anyone who can reach this host, with no authentication. Dot-prefixed"
        yield "paths such as .git are refused; nothing else is."
        yield ""
        yield "If it is not reachable, the port also needs opening on this host."


def serve(root: Path, host: str = LOOPBACK, port: int = 8000) -> ThreadingHTTPServer:
    """Build a server bound to ``host:port`` serving ``root``. Caller runs it."""
    handler = functools.partial(Handler, directory=str(root))
    ThreadingHTTPServer.allow_reuse_address = True
    return ThreadingHTTPServer((host, port), handler)

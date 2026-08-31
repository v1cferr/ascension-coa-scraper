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
import socket
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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


class Handler(SimpleHTTPRequestHandler):
    """Static files, threaded, with the extra types and a dotfile guard."""

    protocol_version = "HTTP/1.1"
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, **EXTRA_TYPES}

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

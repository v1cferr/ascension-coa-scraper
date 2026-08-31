"""The static origin the viewer needs, and what it refuses to hand out."""

from __future__ import annotations

import mimetypes
import threading
import urllib.request
from contextlib import closing

import pytest

from ascension_coa_scraper.serve import (
    ALL_INTERFACES,
    LOOPBACK,
    Handler,
    describe,
    is_hidden,
    serve,
    urls_for,
)


def test_extensions_the_system_does_not_know_are_declared():
    # extensions_map is consulted before mimetypes, so these entries decide the type.
    for ext in (".m2", ".mdx", ".blp", ".skin", ".dbc", ".mpq"):
        assert mimetypes.guess_type("x" + ext)[0] is None, f"{ext} is known after all"
        assert Handler.extensions_map[ext] == "application/octet-stream"


def test_an_extension_the_system_knows_wrongly_is_overridden():
    # The shared mime database claims .wdb is a Microsoft Works document. It is a WoW
    # client cache, and declaring it is what stops the browser being told otherwise.
    assert mimetypes.guess_type("x.wdb")[0] == "application/vnd.ms-works"
    assert Handler.extensions_map[".wdb"] == "application/octet-stream"


@pytest.mark.parametrize("path", ["/.git/config", "/data/../.ssh/id_rsa", "/.env", "/a/.git/x"])
def test_dot_prefixed_segments_are_hidden(path):
    assert is_hidden(path)


@pytest.mark.parametrize("path", ["/web/", "/data/index.json", "/web/app.js", "/a.b/c"])
def test_ordinary_paths_are_not_hidden(path):
    assert not is_hidden(path)


def test_query_strings_do_not_defeat_the_dotfile_guard():
    assert is_hidden("/.git/config?x=1")


def test_loopback_advertises_only_localhost():
    assert urls_for(LOOPBACK, 8000) == ["http://localhost:8000/web/"]


def test_binding_every_interface_advertises_localhost_last(monkeypatch):
    monkeypatch.setattr("ascension_coa_scraper.serve.lan_addresses", lambda: ["192.168.1.10"])
    assert urls_for(ALL_INTERFACES, 8000) == [
        "http://192.168.1.10:8000/web/",
        "http://localhost:8000/web/",
    ]


def test_a_specific_host_is_advertised_as_given():
    assert urls_for("192.168.1.10", 9000) == ["http://192.168.1.10:9000/web/"]


def test_network_binding_says_what_it_exposes(tmp_path, monkeypatch):
    monkeypatch.setattr("ascension_coa_scraper.serve.lan_addresses", lambda: ["10.0.0.5"])
    text = "\n".join(describe(ALL_INTERFACES, 8000, tmp_path))
    assert "10.0.0.5" in text
    assert "no authentication" in text
    assert ".git are refused" in text


def test_loopback_binding_does_not_warn(tmp_path):
    text = "\n".join(describe(LOOPBACK, 8000, tmp_path))
    assert "no authentication" not in text


def test_serves_files_with_the_right_types_and_refuses_a_dotfile(tmp_path):
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "index.html").write_text("<p>ok</p>", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "index.json").write_text("{}", encoding="utf-8")
    (tmp_path / "data" / "bolt.m2").write_bytes(b"MD20")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("secret", encoding="utf-8")

    httpd = serve(tmp_path, host=LOOPBACK, port=0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with closing(urllib.request.urlopen(f"http://{LOOPBACK}:{port}/web/index.html")) as r:
            assert r.status == 200
            assert b"ok" in r.read()
        with closing(urllib.request.urlopen(f"http://{LOOPBACK}:{port}/data/index.json")) as r:
            assert r.headers["Content-Type"] == "application/json"
        with closing(urllib.request.urlopen(f"http://{LOOPBACK}:{port}/data/bolt.m2")) as r:
            assert r.headers["Content-Type"] == "application/octet-stream"
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(f"http://{LOOPBACK}:{port}/.git/config")
        assert caught.value.code == 404
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)

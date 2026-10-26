import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from d0vault.audit import verify
from d0vault.fixture import build_demo
from d0vault.server import ROUTES, make_server
from d0vault.stats import kendall_tau_b, rank_summary, spearman


def test_rank_correlation_on_a_monotone_series():
    xs = [0.1, 0.2, 0.4, 0.8]
    assert spearman(xs, [1, 2, 3, 4]) == pytest.approx(1)
    assert kendall_tau_b(xs, [1, 2, 3, 4]) == pytest.approx(1)
    assert spearman(xs, [4, 3, 2, 1]) == pytest.approx(-1)
    summary = rank_summary([("a", 0.1, 0.2), ("b", 0.4, 0.9), ("c", 0.3, 0.4)])
    assert summary["elected_framework_id"] == "b"
    assert summary["elected_rank"] == 1
    assert summary["regret"] == 0


def test_room_binds_loopback_only(tmp_path):
    with pytest.raises(SystemExit):
        make_server("0.0.0.0", 8502, tmp_path)
    assert all("export" not in route for route in ROUTES)


def _request(port, method, path, body=None, cookie=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(f"http://127.0.0.1:{port}{path}", data=data, method=method)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    if cookie:
        request.add_header("Cookie", cookie)
    try:
        with urlopen(request) as response:
            raw = response.read()
            headers = {key.lower(): value for key, value in response.headers.items()}
            return response.status, headers, json.loads(raw) if raw else None
    except HTTPError as exc:
        raw = exc.read()
        headers = {key.lower(): value for key, value in exc.headers.items()}
        return exc.code, headers, json.loads(raw) if raw else None


def test_one_session_and_a_chained_look_log(tmp_path):
    password = build_demo(tmp_path, password="test-pass")
    assert password == "test-pass"
    assert not (tmp_path / "password.txt").exists()
    server = make_server("127.0.0.1", 0, tmp_path, timeout_s=60)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        status, _headers, body = _request(port, "GET", "/api/board?k=6")
        assert status == 401
        status, headers, body = _request(port, "POST", "/api/login", {"password": "test-pass"})
        assert status == 200 and body["ok"] is True
        cookie = headers["set-cookie"].split(";", 1)[0]
        status, _headers, board = _request(port, "GET", "/api/board?k=6", cookie=cookie)
        assert status == 200
        assert board["ranking"]["elected_framework_id"] == "v5"
        assert board["ranking"]["elected_rank"] == 2
        assert board["ranking"]["regret"] == pytest.approx(0.06)
        assert board["spread"]["f_ideal"]["s0"] == pytest.approx(0.49)
        assert board["k_dagger"] == 5
        assert board["looks"] >= 1
        status, _headers, early = _request(port, "GET", "/api/board?k=3", cookie=cookie)
        assert early["spread"]["f_ideal"] is None
        status, _headers, refused = _request(port, "POST", "/api/login", {"password": "test-pass"})
        assert status == 403
        assert refused["reason"] == "a session is already open"
        audit = tmp_path / "d0_audit.jsonl"
        assert verify(audit)
        text = audit.read_text(encoding="utf-8")
        assert "login_refused" in text
        assert '"user_id": "user"' in text or '"user_id":"user"' in text
        tampered = text.replace("board", "boardX", 1)
        audit.write_text(tampered, encoding="utf-8")
        assert verify(audit) is False
        status, _headers, missing = _request(port, "GET", "/api/export", cookie=cookie)
        assert status == 404
    finally:
        server.shutdown()

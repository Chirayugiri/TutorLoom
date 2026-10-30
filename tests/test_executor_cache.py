from notes2video import cache
from notes2video.executor import run_code


def test_captures_stdout_and_vars():
    r = run_code("xs = [1, 2, 3]\nys = [x * x for x in xs]\nprint('sum', sum(ys))\n")
    assert r.ok and r.stdout == "sum 14\n"
    assert r.vars["ys"] == [1, 4, 9]


def test_network_is_blocked():
    r = run_code("import urllib.request\nurllib.request.urlopen('http://example.com', timeout=2)\n")
    assert not r.ok and "network access is disabled" in r.error


def test_timeout_and_errors_do_not_raise():
    assert "timed out" in run_code("while True: pass\n", timeout_s=2).error
    r = run_code("print('before')\n1/0\n")
    assert not r.ok and r.stdout == "before\n" and "ZeroDivisionError" in r.error


def test_cache_freshness(tmp_path):
    out = tmp_path / "a.txt"
    out.write_text("x")
    k = cache.content_hash("narration", {"voice": "v"})
    assert not cache.is_fresh(out, k)
    cache.mark(out, k)
    assert cache.is_fresh(out, k)
    assert not cache.is_fresh(out, cache.content_hash("narration2", {"voice": "v"}))

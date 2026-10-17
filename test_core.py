"""Run with:  python -m unittest tests.test_core -v

Starts a tiny local website whose content we can change on demand, then checks
that the engine stores a snapshot only when the content really changes.
"""
import http.server
import os
import tempfile
import threading
import unittest

_tmp = tempfile.mkdtemp()
os.environ["TREMOR_DATA"] = _tmp
os.environ["TREMOR_ALLOW_PRIVATE"] = "1"

import db  # noqa: E402  (env must be set first)
from checker import run_check  # noqa: E402
from server import create_app  # noqa: E402

STATE = {"body": "<h1>Price</h1><p>Plan costs 100 rupees</p>", "code": 200}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(STATE["code"])
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<html><head><title>T</title></head><body>{STATE['body']}</body></html>".encode())

    def log_message(self, *a):
        pass


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/"
        cls.client = create_app().test_client()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        STATE.update(body="<h1>Price</h1><p>Plan costs 100 rupees</p>", code=200)
        r = self.client.post("/api/monitors", json={"name": "Test", "url": self.url, "interval_min": 15})
        self.assertEqual(r.status_code, 201)
        self.mid = r.get_json()["id"]

    def snapshots(self):
        return self.client.get(f"/api/monitors/{self.mid}/snapshots").get_json()

    def test_baseline_then_unchanged_then_changed(self):
        self.assertEqual(run_check(self.mid)["outcome"], "baseline")
        self.assertEqual(len(self.snapshots()), 1)

        self.assertEqual(run_check(self.mid)["outcome"], "unchanged")
        self.assertEqual(len(self.snapshots()), 1, "no change must not store a snapshot")

        STATE["body"] = "<h1>Price</h1><p>Plan costs 120 rupees</p>"
        res = run_check(self.mid)
        self.assertEqual(res["outcome"], "changed")
        self.assertTrue(res["changed"])
        self.assertEqual(len(self.snapshots()), 2)

        m = [x for x in self.client.get("/api/monitors").get_json() if x["id"] == self.mid][0]
        self.assertEqual(m["status"], "ok")
        self.assertIsNotNone(m["last_changed"])

    def test_screenshot_saved_with_snapshot(self):
        run_check(self.mid)
        sid = self.snapshots()[0]["id"]
        r = self.client.get(f"/shots/{self.mid}/{sid}.png")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b"\x89PNG"))

    def test_whitespace_only_change_is_not_a_change(self):
        run_check(self.mid)
        STATE["body"] = "<h1>Price</h1>\n\n   <p>Plan   costs 100   rupees</p>"
        self.assertEqual(run_check(self.mid)["outcome"], "unchanged")

    def test_outage_is_not_a_change(self):
        run_check(self.mid)
        STATE.update(code=503, body="Service unavailable")
        res = run_check(self.mid)
        self.assertEqual(res["outcome"], "error")
        self.assertFalse(res["changed"])
        self.assertEqual(len(self.snapshots()), 1)

        STATE.update(code=200, body="<h1>Price</h1><p>Plan costs 100 rupees</p>")
        self.assertEqual(run_check(self.mid)["outcome"], "unchanged", "recovery is not a change")

    def test_captcha_is_blocked_not_changed(self):
        run_check(self.mid)
        STATE.update(code=200, body="<p>Verify you are human. Complete the CAPTCHA.</p>")
        res = run_check(self.mid)
        self.assertEqual(res["outcome"], "blocked")
        self.assertEqual(len(self.snapshots()), 1)

    def test_http_403_is_blocked(self):
        run_check(self.mid)
        STATE.update(code=403, body="Forbidden")
        self.assertEqual(run_check(self.mid)["outcome"], "blocked")

    def test_unreachable_site_is_error(self):
        r = self.client.post("/api/monitors", json={"name": "Dead", "url": "http://127.0.0.1:1/", "interval_min": 15})
        res = run_check(r.get_json()["id"])
        self.assertEqual(res["outcome"], "error")

    def test_validation(self):
        bad = [
            {"name": "x", "url": "ftp://example.com", "interval_min": 60},
            {"name": "x", "url": self.url, "interval_min": 5},
            {"name": "x", "url": self.url, "interval_min": 2000},
            {"name": "", "url": self.url, "interval_min": 60},
        ]
        for body in bad:
            self.assertEqual(self.client.post("/api/monitors", json=body).status_code, 400, body)

    def test_private_addresses_rejected_in_production_mode(self):
        import config, safety
        config.ALLOW_PRIVATE = False
        try:
            for u in ("http://127.0.0.1/", "http://localhost/", "http://169.254.169.254/latest/meta-data"):
                with self.assertRaises(safety.UnsafeURL, msg=u):
                    safety.validate_url(u)
        finally:
            config.ALLOW_PRIVATE = True


if __name__ == "__main__":
    unittest.main()

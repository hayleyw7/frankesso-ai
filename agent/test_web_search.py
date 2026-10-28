import unittest
from unittest.mock import patch

import web_search


class Response:
    status = 200
    data = b'<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.python.org%2Fdoc%2F">Python documentation</a>'
    def getheader(self, name, default=""):
        return "text/html; charset=utf-8"
    def read(self, count):
        return self.data[:count]


class Connection:
    def __init__(self, response):
        self.response = response
        self.requests = []
        self.closed = False
    def request(self, *args, **kwargs):
        self.requests.append((args, kwargs))
    def getresponse(self):
        return self.response
    def close(self):
        self.closed = True


class WebTests(unittest.TestCase):
    def test_denial_never_constructs_connection_or_resolves_dns(self):
        with patch("socket.getaddrinfo", side_effect=AssertionError("DNS forbidden")), patch("http.client.HTTPSConnection", side_effect=AssertionError("Network forbidden")):
            result = web_search.search("Python official documentation", lambda *_: False)
        self.assertTrue(result["denied"])
        self.assertFalse(result["network_request"])

    def test_each_request_requires_fresh_approval(self):
        connection = Connection(Response())
        decisions = iter([False, True, False])
        prompts = []
        def approval(action, details):
            prompts.append(details)
            return next(decisions)
        for _ in range(3):
            web_search.search("Python official documentation", approval, lambda *a, **k: connection)
        self.assertEqual(len(prompts), 3)
        self.assertEqual(len(connection.requests), 1)
        self.assertIn("https://html.duckduckgo.com/html/", prompts[0])
        self.assertIn("q=Python+official+documentation", prompts[0])

    def test_approved_exact_request_and_offline_result_parsing(self):
        connection = Connection(Response())
        result = web_search.search("Python official documentation", lambda *_: True, lambda *a, **k: connection)
        args, kwargs = connection.requests[0]
        self.assertEqual(args, ("POST", "/html/"))
        self.assertEqual(kwargs["body"], b"q=Python+official+documentation")
        self.assertEqual(result["results"], [{"title": "Python documentation", "url": "https://www.python.org/doc/"}])
        self.assertTrue(connection.closed)

    def test_redirect_not_followed(self):
        response = Response()
        response.status = 302
        connection = Connection(response)
        result = web_search.search("test", lambda *_: True, lambda *a, **k: connection)
        self.assertIn("NOT followed", result["error"])
        self.assertEqual(len(connection.requests), 1)

    def test_failure_no_retry(self):
        calls = []
        def fail(*args, **kwargs):
            calls.append(1)
            raise OSError("offline")
        result = web_search.search("test", lambda *_: True, fail)
        self.assertIn("error", result)
        self.assertEqual(len(calls), 1)

    def test_large_response_is_rejected(self):
        response = Response()
        response.data = b"x" * (web_search.MAX_RESPONSE + 1)
        result = web_search.search("test", lambda *_: True, lambda *a, **k: Connection(response))
        self.assertIn("size limit", result["error"])

    def test_no_result_page_fetch_or_script_execution(self):
        response = Response()
        response.data = b'<script>fetch("https://example.com")</script><a class="result__a" href="javascript:alert(1)">bad</a>'
        connection = Connection(response)
        result = web_search.search("test", lambda *_: True, lambda *a, **k: connection)
        self.assertEqual(result["results"], [])
        self.assertEqual(len(connection.requests), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

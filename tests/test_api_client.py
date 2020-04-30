import unittest
from unittest import mock
from unittest.mock import Mock

from opentelemetry.ext.lightstep.api_client import APIClient
from opentelemetry.ext.lightstep.version import __version__


class TestAPIClient(unittest.TestCase):
    @mock.patch("requests.post")
    def test_request_headers(self, mock_post):
        m = Mock()

        def side_effect(*args, **kwargs):
            m.headers = kwargs.get("headers")
            m.status_code = 200
            return m

        mock_post.side_effect = side_effect
        APIClient("123", "test.com").send("content")

        expected = {
            "User-Agent": "otel-ls-python/{}".format(__version__),
            "Accept": "application/octet-stream",
            "Content-Type": "application/octet-stream",
            "Lightstep-Access-Token": "123",
        }
        mock_post.assert_called()

        self.assertEqual(len(m.headers), len(expected))
        self.assertEqual(m.headers, expected)

        expected["Lightstep-Access-Token"] = "other"
        mock_post.assert_called()
        APIClient("123", "test.com").send("content", "other")

        self.assertEqual(len(m.headers), len(expected))
        self.assertEqual(m.headers, expected)

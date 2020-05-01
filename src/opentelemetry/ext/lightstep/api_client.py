import backoff
import requests

from opentelemetry.ext.lightstep.version import __version__


class APIClient:
    """HTTP client to send data to Lightstep"""

    def __init__(
        self, token, url,
    ):
        self._headers = {
            "User-Agent": "otel-ls-python/{}".format(__version__),
            "Accept": "application/octet-stream",
            "Content-Type": "application/octet-stream",
            "Lightstep-Access-Token": token,
        }
        self._url = url

    @backoff.on_exception(backoff.expo, Exception, max_time=5)
    def send(self, content, token=None):
        if token is not None:
            self._headers["Lightstep-Access-Token"] = token

        return requests.post(self._url, headers=self._headers, data=content)

import ssl
import urllib.request
from urllib import parse

import m3u8  # type: ignore
import requests  # type: ignore
from requests.adapters import HTTPAdapter  # type: ignore
from urllib3.poolmanager import PoolManager


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "AppleWebKit/537.36 (KHTML, like Gecko)",
    "Chrome/126.0.0.0",
    "Safari/537.36",
]

REQUEST_HEADER = {"User-Agent": ""}


class TLSAdapter(HTTPAdapter):

    def init_poolmanager(self, connections, maxsize, block=False, **_) -> None:
        """Create and initialize the PoolManager."""
        ctx = ssl.create_default_context()
        ctx.options |= (
            ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_LEGACY_SERVER_CONNECT
        )  # For Python 3.6+
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_version=ssl.PROTOCOL_TLS,  # Force TLS 1.2
            ssl_context=ctx,
        )


class LegacyM3U8Client(m3u8.DefaultHTTPClient):

    def download(self, uri, timeout=None, headers=None, _=...):
        headers = headers or {}
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.options |= (
            ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_LEGACY_SERVER_CONNECT
        )
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        proxy_handler = urllib.request.ProxyHandler(self.proxies)
        https_handler = urllib.request.HTTPSHandler(context=ctx)
        opener = urllib.request.build_opener(proxy_handler, https_handler)
        opener.addheaders = headers.items()
        resource = opener.open(uri, timeout=timeout)
        base_uri = parse.urljoin(resource.geturl(), ".")
        content = resource.read().decode(
            resource.headers.get_content_charset(failobj="utf-8")
        )
        return content, base_uri


def new_legacy_session() -> requests.Session:
    s = requests.session()
    s.mount("https://", TLSAdapter())
    return s

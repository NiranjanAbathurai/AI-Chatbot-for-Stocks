"""
SSL certificate verification fix for environments with corporate proxies
or self-signed certificates in the chain.

Import this module early (before other imports) to disable strict SSL
verification globally. This is only intended for LOCAL DEVELOPMENT.
"""

import os
import ssl
import warnings

# Suppress SSL-related warnings
warnings.filterwarnings("ignore", message=".*ssl.*", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*certificate.*")
warnings.filterwarnings("ignore", message=".*Unverified HTTPS.*")

# Disable SSL verification globally via environment variables
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["SSL_CERT_FILE"] = ""
os.environ["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"

# Patch ssl default context to not verify certificates
_original_create_default_context = ssl.create_default_context


def _create_unverified_context(*args, **kwargs):
    ctx = _original_create_default_context(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


ssl.create_default_context = _create_unverified_context
ssl._create_default_https_context = ssl._create_unverified_context


# Patch aiohttp to use unverified SSL
def _patch_aiohttp():
    """Patch aiohttp.TCPConnector to disable SSL verification by default."""
    try:
        import aiohttp

        _original_tcp_init = aiohttp.TCPConnector.__init__

        def _patched_tcp_init(self, *args, **kwargs):
            if "ssl" not in kwargs:
                kwargs["ssl"] = False
            _original_tcp_init(self, *args, **kwargs)

        aiohttp.TCPConnector.__init__ = _patched_tcp_init
    except ImportError:
        pass


# Patch httpx to use unverified SSL
def _patch_httpx():
    """Patch httpx clients to disable SSL verification by default."""
    try:
        import httpx

        _original_client_init = httpx.Client.__init__
        _original_async_client_init = httpx.AsyncClient.__init__

        def _patched_client_init(self, *args, **kwargs):
            if "verify" not in kwargs:
                kwargs["verify"] = False
            _original_client_init(self, *args, **kwargs)

        def _patched_async_client_init(self, *args, **kwargs):
            if "verify" not in kwargs:
                kwargs["verify"] = False
            _original_async_client_init(self, *args, **kwargs)

        httpx.Client.__init__ = _patched_client_init
        httpx.AsyncClient.__init__ = _patched_async_client_init
    except ImportError:
        pass


# Patch httpx2 (used by google-genai)
def _patch_httpx2():
    """Patch httpx2 clients to disable SSL verification by default."""
    try:
        import httpx2

        _original_client_init = httpx2.Client.__init__
        _original_async_client_init = httpx2.AsyncClient.__init__

        def _patched_client_init(self, *args, **kwargs):
            if "verify" not in kwargs:
                kwargs["verify"] = False
            _original_client_init(self, *args, **kwargs)

        def _patched_async_client_init(self, *args, **kwargs):
            if "verify" not in kwargs:
                kwargs["verify"] = False
            _original_async_client_init(self, *args, **kwargs)

        httpx2.Client.__init__ = _patched_client_init
        httpx2.AsyncClient.__init__ = _patched_async_client_init
    except ImportError:
        pass


# Apply all patches
_patch_aiohttp()
_patch_httpx()
_patch_httpx2()

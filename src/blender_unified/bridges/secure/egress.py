"""Outbound HTTP gate for the BlenderMCP addon (SSRF guard + file validation).

This module is dependency-free (``requests`` is imported lazily) so the pure
validation helpers can be unit-tested without network access or Blender.

It is the authoritative egress check for the addon: the MCP server only
performs an early, friendlier copy of the URL check before forwarding URLs to
Blender. This is a footgun-reducer, not a sandbox - it blocks requests to
loopback/private/link-local/metadata endpoints and rejects files whose content
does not match their expected format.
"""
import ipaddress
import socket
from urllib.parse import urlparse


class EgressError(Exception):
    """Raised when an outbound request fails an egress validation check."""

# Per-integration allow-list of hosts. CDN/download hosts returned by an API
# are added at runtime by callers and are still subject to the DNS/IP checks.
EGRESS_ALLOWED_HOSTS = {
    "polyhaven": {"api.polyhaven.com"},
    "sketchfab": {"api.sketchfab.com", "media.sketchfab.com"},
    "hyper3d_main": {"hyperhuman.deemos.com"},
    "hyper3d_fal": {"queue.fal.run", "fal.run"},
    "hunyuan_official": {"hunyuan.tencentcloudapi.com"},
}

# Rough ceiling for a single integration download; call sites may lower it.
EGRESS_MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024  # 256 MiB

# Magic-byte signatures for formats the addon is willing to import. Values are
# raw hex (see ROADMAP, Epic 2) except the ASCII signatures (HDR/GLB).
_EGRESS_MAGIC_BYTES = {
    "png": bytes.fromhex("89504e470d0a1a0a"),  # 89 50 4E 47 0D 0A 1A 0A
    "jpeg": bytes.fromhex("ffd8ff"),           # FF D8 FF
    "exr": bytes.fromhex("762f3101"),          # 76 2F 31 01
    "hdr": (b"#?RADIANCE", b"#?RGBE"),
    "glb": b"glTF",                            # 67 6C 54 46
    "zip": bytes.fromhex("504b0304"),          # 50 4B 03 04
}


def classify_ip(ip_str):
    """Return a reason string if ``ip_str`` must be rejected, else ``None``."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return "unresolvable"
    # Order matters: several families overlap (e.g. 169.254/16 is both
    # link-local and private, 0.0.0.0 is both unspecified and private). Check
    # the most specific labels first so callers get an accurate reason.
    if ip.is_loopback:
        return "loopback"
    if ip.is_link_local:
        return "link-local"
    if ip.is_unspecified:
        return "unspecified"
    if ip.is_multicast:
        return "multicast"
    if ip.is_reserved:
        return "reserved"
    if ip.is_private:
        return "private"
    return None


def host_allowed(host, allowed_hosts=None, allow_private=False, allow_loopback=False):
    """Resolve ``host`` and reject forbidden address families.

    Returns ``(ok, reason)``. ``allowed_hosts`` is an iterable of allowed
    hostnames (exact or subdomain match). Pass ``None`` to skip the hostname
    allow-list; resolved IP addresses are always checked.
    """
    host = (host or "").strip().lower()
    if not host:
        return False, "empty host"

    if allowed_hosts is not None:
        allowed = [a.strip().lower() for a in allowed_hosts if a and a.strip()]
        if allowed and not any(h == host or host.endswith("." + h) for h in allowed):
            return False, "host not allowed"

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError as e:
        return False, f"cannot resolve host: {e}"

    addrs = {info[4][0] for info in infos}
    for addr in addrs:
        reason = classify_ip(addr)
        if reason is None:
            continue
        if reason == "loopback" and allow_loopback:
            continue
        if reason == "private" and allow_private:
            continue
        return False, f"forbidden address ({reason}): {addr}"
    return True, None


def validate_url(url, allowed_hosts=None, allow_private=False, allow_loopback=False):
    """Validate a URL for outbound use. Returns ``(ok, reason)``.

    Enforces http/https, an optional host allow-list, and rejects hosts that
    resolve to loopback/private/link-local/multicast/reserved/unspecified IPs.
    """
    try:
        parsed = urlparse(url or "")
    except ValueError:
        return False, "unparseable URL"
    if parsed.scheme not in {"http", "https"}:
        return False, f"unsupported scheme: {parsed.scheme!r}"
    if not parsed.hostname:
        return False, "missing host"
    if parsed.username or parsed.password:
        return False, "userinfo not allowed in URL"
    return host_allowed(parsed.hostname, allowed_hosts, allow_private, allow_loopback)


def validate_download(data, expected_formats):
    """Check ``data`` against magic-byte signatures.

    ``expected_formats`` is an iterable of keys from ``_EGRESS_MAGIC_BYTES``.
    Returns ``(ok, reason)``.
    """
    if not isinstance(data, (bytes, bytearray)):
        return False, "expected bytes"
    data = bytes(data)
    if not data:
        return False, "empty data"
    for fmt in expected_formats:
        sig = _EGRESS_MAGIC_BYTES.get(fmt)
        if sig is None:
            continue
        prefixes = sig if isinstance(sig, tuple) else (sig,)
        if any(data.startswith(p) for p in prefixes):
            return True, None
    return False, f"content does not match expected format(s): {sorted(expected_formats)}"


def read_bounded(iter_chunks, max_bytes):
    """Read ``iter_chunks`` (bytes chunks) into one ``bytes`` with a size cap.

    Returns ``(data, None)`` on success or ``(None, reason)`` on overflow.
    """
    parts = []
    total = 0
    for chunk in iter_chunks:
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            return None, f"download exceeds {max_bytes} bytes"
        parts.append(chunk)
    return b"".join(parts), None


def fetch(url, allowed_hosts=None, allow_private=False, allow_loopback=False,
          max_bytes=EGRESS_MAX_DOWNLOAD_BYTES, timeout=30):
    """Fetch ``url`` with egress validation, redirects disabled, and a size cap.

    Returns ``(bytes, None)`` on success or ``(None, reason)`` on failure.
    ``requests`` is imported lazily so the pure validators stay dependency-free.
    """
    ok, reason = validate_url(url, allowed_hosts, allow_private, allow_loopback)
    if not ok:
        return None, reason

    import requests
    try:
        resp = requests.get(url, stream=True, timeout=timeout, allow_redirects=False)
    except requests.exceptions.RequestException as e:
        return None, f"request failed: {e}"
    try:
        if resp.status_code != 200:
            return None, f"unexpected status {resp.status_code}"
        return read_bounded(resp.iter_content(chunk_size=8192), max_bytes)
    finally:
        resp.close()


def download(url, dest_path, allowed_hosts=None, allow_private=False,
             allow_loopback=False, max_bytes=EGRESS_MAX_DOWNLOAD_BYTES,
             timeout=30, expected_formats=None):
    """Download ``url`` to ``dest_path``, verifying magic bytes when requested.

    Returns ``(ok, reason)``.
    """
    data, reason = fetch(url, allowed_hosts, allow_private, allow_loopback,
                         max_bytes, timeout)
    if data is None:
        return False, reason
    if expected_formats:
        ok, reason = validate_download(data, expected_formats)
        if not ok:
            return False, reason
    try:
        with open(dest_path, "wb") as f:
            f.write(data)
    except OSError as e:
        return False, f"cannot write download: {e}"
    return True, None


def request(method, url, allowed_hosts=None, allow_private=False, allow_loopback=False,
            timeout=30, **kwargs):
    """Perform a validated HTTP request and return the ``requests.Response``.

    Raises ``EgressError`` if the URL fails validation (scheme, allow-list, or a
    forbidden resolved address). Request-level exceptions (timeout, connection
    errors) propagate untouched so callers can handle them specifically.
    Redirects are disabled.
    """
    ok, reason = validate_url(url, allowed_hosts, allow_private, allow_loopback)
    if not ok:
        raise EgressError(reason)

    import requests
    return requests.request(method, url, timeout=timeout, allow_redirects=False, **kwargs)

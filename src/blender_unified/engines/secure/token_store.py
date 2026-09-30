"""Auth-token resolution and client-side caching for the BlenderMCP server.

This module is intentionally free of any ``mcp`` dependency so it can be
unit-tested in isolation (see ``test_token_resolution.py``).

Token resolution priority (see :func:`token_candidates` / :func:`resolve_token`):

1. ``BLENDERMCP_TOKEN``      - literal token. Empty values *and obvious
                               placeholders* (unedited README examples such as
                               ``<input-your-token-here>`` or "Input your token
                               here") are ignored, so a stock config behaves as
                               if the variable were unset.
2. ``BLENDERMCP_TOKEN_FILE`` - explicit path to a token file (empty and
                               placeholder contents ignored).
3. The MCP-side token cache  - the last known-good token for this host:port,
                               written after a successful authentication. This
                               is what makes reconnects zero-config: the MCP
                               server persists the token itself and does not
                               need write access to the client's settings.
4. The addon's temporary ``blendermcp_token_<port>`` file.

If none of these yields a token, the caller (``server.py``) falls back to
loopback socket pairing. The caller tries every candidate in order: a token
rejected by the addon (``invalid token``) does not abort the attempt - the
next source is tried, ending with pairing.
"""
from __future__ import annotations

import logging
import os
import sys
import tempfile

logger = logging.getLogger("BlenderMCPTokenStore")


# --------------------------------------------------------------------------- #
# MCP-side token cache
# --------------------------------------------------------------------------- #


def _cache_dir() -> str:
    """Per-user directory where the MCP server caches known-good tokens.

    ``BLENDERMCP_CACHE_DIR`` overrides the default location (also handy for
    tests). Otherwise a conventional per-platform cache directory is used.
    """
    override = os.getenv("BLENDERMCP_CACHE_DIR")
    if override and override.strip():
        return override.strip()
    if os.name == "nt":
        base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "blender-mcp")
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Caches", "blender-mcp")
    xdg = os.getenv("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(xdg, "blender-mcp")


def _token_cache_path(host: str, port: int) -> str:
    """Cache file for a given endpoint. The host is sanitized for the FS."""
    safe_host = "".join(c if c.isalnum() else "_" for c in (host or "")) or "host"
    return os.path.join(_cache_dir(), f"token_{safe_host}_{port}")


def save_token_cache(host: str, port: int, token: str) -> None:
    """Persist a known-good token with restrictive permissions.

    The write is skipped when the cache already holds this exact token, so it
    is cheap to call on every successful command.
    """
    if not token:
        return
    path = _token_cache_path(host, port)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "r", encoding="utf-8") as f:
                if f.read().strip() == token:
                    return  # already cached - nothing to do
        except OSError:
            pass
        if os.name != "nt":
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(token)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(token)
        logger.info(f"Cached auth token to {path}")
    except OSError as e:
        logger.warning(f"Could not write token cache {path}: {e}")


def read_token_cache(host: str, port: int) -> str | None:
    """Return the cached token for an endpoint, if any."""
    path = _token_cache_path(host, port)
    try:
        with open(path, "r", encoding="utf-8") as f:
            token = f.read().strip()
        if token:
            logger.info(f"Using cached auth token from {path}")
            return token
    except OSError:
        pass
    return None


def invalidate_token_cache(host: str, port: int) -> None:
    """Drop a cached token (e.g. after the addon reports ``invalid token``)."""
    path = _token_cache_path(host, port)
    try:
        os.remove(path)
        logger.info(f"Invalidated stale auth token cache {path}")
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Addon temporary token file
# --------------------------------------------------------------------------- #


def _candidate_token_dirs() -> list[str]:
    """Directories that may contain the addon's ``blendermcp_token_<port>`` file.

    The addon writes the token to *its own* ``tempfile.gettempdir()``. On
    Windows the MCP server process can resolve ``tempfile.gettempdir()`` to a
    different directory than Blender (different TEMP/TMP environment), so
    relying on a single path is not reliable. Probe a set of well-known
    locations instead; missing ones are simply skipped.
    """
    dirs: list[str] = [tempfile.gettempdir()]
    # Common Windows temp roots (Blender may run under a different TEMP than us).
    dirs.append(r"C:\Temp")
    dirs.append(r"C:\Windows\Temp")
    user_profile = os.getenv("USERPROFILE") or os.path.expanduser("~")
    if user_profile:
        dirs.append(os.path.join(user_profile, "AppData", "Local", "Temp"))
    # POSIX fallback.
    dirs.append("/tmp")

    seen: set[str] = set()
    unique: list[str] = []
    for d in dirs:
        if d and d not in seen:
            seen.add(d)
            unique.append(d)
    return unique


def _read_addon_token_file(port: int) -> str | None:
    """Read the most recent ``blendermcp_token_<port>`` file the addon wrote.

    Preferring the newest file lets a fresh token written by the live addon win
    over a stale copy left behind in another directory.
    """
    filename = f"blendermcp_token_{port}"
    best_path: str | None = None
    best_mtime = -1.0
    for d in _candidate_token_dirs():
        path = os.path.join(d, filename)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if mtime > best_mtime:
            best_mtime = mtime
            best_path = path

    if best_path is None:
        return None

    try:
        with open(best_path, "r", encoding="utf-8") as f:
            token = f.read().strip()
        logger.info(f"Read BlenderMCP auth token from {best_path}")
        return token
    except (OSError, IOError):
        return None


# --------------------------------------------------------------------------- #
# Placeholder detection
# --------------------------------------------------------------------------- #

# Keywords that, combined with "token"/"токен", mark an unedited README
# example rather than a real secret. Real tokens are long hex strings and can
# never trip this.
_PLACEHOLDER_MARKERS = (
    "insert",
    "input",
    "paste",
    "enter",
    "type",
    "replace",
    "change",
    "your",
    "here",
    "example",
    "sample",
    "placeholder",
    "changeme",
    "xxxx",
    "dummy",
    "todo",
    "fixme",
    "встав",
    "впиш",
    "введ",
    "замен",
    "сюда",
    "пример",
)


def is_placeholder(value: str | None) -> bool:
    """Detect empty/placeholder token values (e.g. an unedited README example).

    Such values are ignored during resolution, so a config that still carries
    ``"BLENDERMCP_TOKEN": "<input-your-token-here>"`` behaves exactly like an
    unset variable and falls back to zero-config resolution/pairing.

    To avoid discarding valid custom tokens, a non-empty value is only treated
    as a placeholder when it mentions a token (``token``/``токен``) *and* looks
    like an unedited README example: an angle-bracket template (``<...>``) or a
    prose instruction containing one of the placeholder marker words. A bare
    ``<...>`` without a token word is treated as a real secret.
    """
    v = (value or "").strip()
    if not v:
        return True
    low = v.lower()
    if "token" not in low and "токен" not in low:
        return False
    if v.startswith("<") and v.endswith(">"):
        return True
    if any(m in low for m in _PLACEHOLDER_MARKERS):
        return True
    return False


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #


def token_candidates(host: str, port: int) -> list[tuple[str, str]]:
    """All candidate tokens in priority order as ``(source_label, token)``.

    See the module docstring for the order. Empty values and obvious
    placeholders are skipped; duplicate token values are removed (first source
    wins), since re-trying an identical token can never change the outcome.
    """
    raw: list[tuple[str, str]] = []

    literal = (os.getenv("BLENDERMCP_TOKEN") or "").strip()
    if literal:
        raw.append(("BLENDERMCP_TOKEN environment variable", literal))

    explicit = (os.getenv("BLENDERMCP_TOKEN_FILE") or "").strip()
    if explicit:
        try:
            with open(explicit, "r", encoding="utf-8") as f:
                token = f.read().strip()
            if token:
                raw.append((f"BLENDERMCP_TOKEN_FILE ({explicit})", token))
            else:
                logger.warning(f"BLENDERMCP_TOKEN_FILE is empty: {explicit}")
        except (OSError, IOError):
            logger.warning(f"BLENDERMCP_TOKEN_FILE is set but unreadable: {explicit}")

    cached = read_token_cache(host, port)
    if cached:
        raw.append(("MCP token cache", cached))

    addon_file = _read_addon_token_file(port)
    if addon_file:
        raw.append(("addon token file", addon_file))

    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for label, token in raw:
        if is_placeholder(token):
            logger.info(f"Ignoring placeholder token value from {label}")
            continue
        if token in seen:
            continue
        seen.add(token)
        candidates.append((label, token))
    return candidates


def resolve_token(host: str, port: int) -> str | None:
    """Resolve the first candidate auth token for the addon.

    Returns ``None`` when no source yields a usable token; the caller then
    attempts loopback socket pairing.
    """
    candidates = token_candidates(host, port)
    if not candidates:
        return None
    label, token = candidates[0]
    logger.info(f"Using auth token from {label}")
    return token

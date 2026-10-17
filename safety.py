"""Validates URLs before we fetch them. Public web pages only."""
import ipaddress
import socket
from urllib.parse import urlparse

import config


class UnsafeURL(ValueError):
    pass


def _is_public(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return not (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_reserved or addr.is_multicast or addr.is_unspecified)


def validate_url(url: str) -> str:
    """Returns the cleaned URL or raises UnsafeURL."""
    url = (url or "").strip()
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UnsafeURL("URL must start with http:// or https://")
    if parts.username or parts.password:
        raise UnsafeURL("URLs with a username or password are not allowed")
    if config.ALLOW_PRIVATE:
        return url
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443)
    except socket.gaierror:
        raise UnsafeURL("Could not find that website")
    if not all(_is_public(i[4][0]) for i in infos):
        raise UnsafeURL("Only public websites can be monitored")
    return url

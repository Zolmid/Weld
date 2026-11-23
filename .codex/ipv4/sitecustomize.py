"""Opt-in IPv4 DNS results for this Mac's dependency downloads only."""

import os
import socket

if os.environ.get("BRAVE_FETCH_IPV4_ONLY") == "1":
    _original_getaddrinfo = socket.getaddrinfo

    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if family == socket.AF_UNSPEC:
            family = socket.AF_INET
        return _original_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = _ipv4_getaddrinfo

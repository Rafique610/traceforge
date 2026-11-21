import socket

import pytest


def test_network_is_off():
    with pytest.raises(OSError):
        socket.create_connection(("1.1.1.1", 53), timeout=3)


def test_dns_is_off():
    with pytest.raises(OSError):
        socket.getaddrinfo("example.com", 80)

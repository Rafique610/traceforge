# ruff: noqa: E501
"""Source text of a tiny in-process RESP server (conftest helper) used by broker-related tests.

It answers HELLO with a RESP3 map, PING with +PONG, LPUSH with :1 and anything else with +OK, records commands, and listens on loopback,
which exists even in the sandbox's `--network none` container. It is a test double, labelled as such.
"""

BROKER_CONFTEST = r'''"""Test plumbing: a loopback stand-in for the broker (test double, records commands)."""

import socketserver
import threading

import pytest


class _Handler(socketserver.StreamRequestHandler):
    def _command(self):
        head = self.rfile.readline()
        if not head:
            return None
        parts = []
        for _ in range(int(head[1:])):
            size = int(self.rfile.readline()[1:])
            parts.append(self.rfile.read(size + 2)[:-2].decode())
        return parts

    def handle(self):
        while (cmd := self._command()) is not None:
            self.server.commands.append(cmd)
            name = cmd[0].upper()
            if name == "HELLO":  # RESP3 handshake sent by recent client versions
                self.wfile.write(b"%2\r\n$6\r\nserver\r\n$4\r\nstub\r\n$5\r\nproto\r\n:3\r\n")
            elif name == "PING":
                self.wfile.write(b"+PONG\r\n")
            elif name == "LPUSH":
                self.wfile.write(b":1\r\n")
            else:
                self.wfile.write(b"+OK\r\n")
            self.wfile.flush()


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


@pytest.fixture
def broker():
    """Factory: broker(port) starts a stand-in listening on 127.0.0.1:<port>; returns its command log."""
    servers = []

    def start(port):
        srv = _Server(("127.0.0.1", port), _Handler)
        srv.commands = []
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return srv.commands

    yield start
    for srv in servers:
        srv.shutdown()
        srv.server_close()
'''

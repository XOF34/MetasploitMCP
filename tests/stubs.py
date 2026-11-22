#!/usr/bin/env python3
"""
Shared stand-ins for MetasploitMCP's third-party dependencies.

MetasploitMCP is imported only once per test session, and what it binds at
import time sticks: the FastMCP ``tool()`` decorator wraps every tool function,
and ``MsfRpcError`` / ``MsfConsole`` are the classes its ``except`` and
``isinstance`` checks use. If each test file installed its own stubs, whichever
file imported MetasploitMCP first would decide those bindings for all the
others. So the stubs are defined once here, and ``install()`` puts the same
objects into ``sys.modules`` every time it is called.

``conftest.py`` calls ``install()`` before collection. Test files call it as
well, so running one directly (``python tests/test_helpers.py``) still works.
"""

import sys
import types
from unittest.mock import Mock


class FastMCP:
    """Stand-in for ``mcp.server.fastmcp.FastMCP``.

    ``tool()`` returns the decorated function unchanged, so tests can await the
    real tool coroutines.
    """

    def __init__(self, *args, **kwargs):
        pass

    def tool(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator


class MsfRpcError(Exception):
    """Stand-in for ``pymetasploit3.msfrpc.MsfRpcError``."""


class MsfConsole:
    """Stand-in for ``pymetasploit3.msfrpc.MsfConsole``."""

    def __init__(self, cid='test-console-id'):
        self.cid = cid

    def read(self):
        return {'data': '', 'prompt': 'msf6 > ', 'busy': False}

    def write(self, command):
        return True


class MsfRpcClient:
    """Stand-in for ``pymetasploit3.msfrpc.MsfRpcClient``."""

    def __init__(self, *args, **kwargs):
        self.modules = Mock()
        self.core = Mock()
        self.sessions = Mock()
        self.jobs = Mock()
        self.consoles = Mock()


def _module(name, **attributes):
    module = types.ModuleType(name)
    module.__dict__.update(attributes)
    return module


STUB_MODULES = {
    'uvicorn': Mock(),
    'fastapi': Mock(),
    'mcp.server.fastmcp': _module('mcp.server.fastmcp', FastMCP=FastMCP),
    'mcp.server.sse': Mock(),
    'mcp.server.session': Mock(),
    'pymetasploit3.msfrpc': _module(
        'pymetasploit3.msfrpc',
        MsfConsole=MsfConsole,
        MsfRpcClient=MsfRpcClient,
        MsfRpcError=MsfRpcError,
    ),
    'starlette.applications': Mock(),
    'starlette.routing': Mock(),
}


def install():
    """Put the shared stubs into ``sys.modules``. Safe to call repeatedly."""
    sys.modules.update(STUB_MODULES)

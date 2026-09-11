#!/usr/bin/env python3
"""Compatibility entry point for MCP configs that still launch this file.

Prefer `infinitebacklog-mcp` or `python -m infinitebacklog_mcp.server` after
`pip install -e .`.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from infinitebacklog_mcp.server import main, mcp  # noqa: F401

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""兼容入口；统一命令见 python -m evesde --help。"""
import sys
from evesde.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["build", *sys.argv[1:]]))

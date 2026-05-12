#!/usr/bin/env python3
"""
Compatibility wrapper for the old onboarding command.

Use scripts/add_stock.py for new work. This wrapper keeps existing commands
working while routing the flow through the unified onboarding entrypoint.
"""
import os
import subprocess
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Compatibility wrapper; delegates to scripts/add_stock.py",
        add_help=True,
    )
    parser.add_argument("stock_code", nargs="?")
    parser.add_argument("stock_name", nargs="?")
    args, extra = parser.parse_known_args()

    if not args.stock_code:
        parser.print_help()
        return 2

    script_dir = os.path.dirname(os.path.abspath(__file__))
    add_stock = os.path.join(script_dir, "add_stock.py")
    command = [sys.executable, add_stock, args.stock_code]
    if args.stock_name:
        command.append(args.stock_name)
    command.extend(extra)
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

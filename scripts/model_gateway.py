#!/usr/bin/env python3
"""
Unified model gateway.

All external LLM calls must be routed through this module. High-frequency
polling jobs must not import or execute this file. The gateway first applies
cheap deterministic checks so empty/no-op inputs never spend model tokens.
"""
import argparse
import json
import os
import sys


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def should_call_model(payload):
    if not payload:
        return False, "empty payload"

    if "has_new" in payload and not payload.get("has_new"):
        return False, "poll result has no new announcements"

    new_count = payload.get("new_count")
    if new_count is not None and int(new_count) <= 0:
        return False, "poll result new_count is zero"

    if not payload.get("results") and not payload.get("new_announcements"):
        return False, "no analysis candidates"

    return True, "model call allowed"


def run_model(payload, provider):
    """
    Placeholder for necessary model calls.

    Implement providers here, not in polling/data-fetch scripts. Keep provider
    calls behind should_call_model() and explicit manual workflow invocation.
    """
    raise NotImplementedError(
        f"model provider '{provider}' is not configured; "
        "add provider implementation inside scripts/model_gateway.py"
    )


def main():
    parser = argparse.ArgumentParser(description="Unified gated model entrypoint")
    parser.add_argument("--input", required=True, help="JSON payload to analyze")
    parser.add_argument(
        "--provider",
        default=os.environ.get("MODEL_PROVIDER", "none"),
        help="model provider configured inside this gateway",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="evaluate gating without calling a model",
    )
    args = parser.parse_args()

    payload = load_json(args.input)
    allowed, reason = should_call_model(payload)
    print(json.dumps({"allowed": allowed, "reason": reason}, ensure_ascii=False))

    if not allowed:
        return 0

    if args.dry_run:
        return 0

    try:
        run_model(payload, args.provider)
    except NotImplementedError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

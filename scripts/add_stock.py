#!/usr/bin/env python3
"""
One-command stock onboarding.

The script first ensures config/stocks.json contains the stock, then runs the
selected incremental pipeline steps. It does not call any model.
"""
import argparse
import json
import os
import subprocess
import sys

from cninfo_resolver import resolve_stock_info
from stock_config import DEFAULT_STOCK_CONFIG

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_STEPS = [
    "config",
    "history",
    "pdfs",
    "extract-pdfs",
    "akshare",
    "entities",
    "rag",
]

STEP_CHOICES = DEFAULT_STEPS + ["neo4j"]


def load_config(path):
    if not os.path.exists(path):
        return {"stocks": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def ensure_stock_config(code, name, config_path):
    config = load_config(config_path)
    stocks = config.setdefault("stocks", [])
    for stock in stocks:
        if str(stock.get("code")) == code:
            if name and stock.get("name") != name:
                stock["name"] = name
                save_config(config_path, config)
                return name, "updated"
            return stock.get("name") or name or code, "exists"

    if not name:
        name = resolve_stock_info(code).get("name") or code
    stocks.append({"code": code, "name": name})
    save_config(config_path, config)
    return name, "added"


def inspect_stock_config(code, name, config_path):
    config = load_config(config_path)
    for stock in config.get("stocks", []):
        if str(stock.get("code")) == code:
            current_name = stock.get("name") or name or code
            if name and current_name != name:
                return name, "would update"
            return current_name, "exists"

    if not name:
        name = resolve_stock_info(code).get("name") or code
    return name, "would add"


def run_step(step, code, name, args):
    script = os.path.join(PROJECT_ROOT, "scripts")
    commands = {
        "history": [sys.executable, os.path.join(script, "fetch_history.py"), code, name],
        "pdfs": [sys.executable, os.path.join(script, "fetch_pdfs.py"), code, args.filing_type],
        "extract-pdfs": [sys.executable, os.path.join(script, "extract_pdfs.py")],
        "akshare": [sys.executable, os.path.join(script, "fetch_akshare.py")],
        "entities": [sys.executable, os.path.join(script, "extract_entities.py"), "extract"],
        "rag": [sys.executable, os.path.join(script, "build_rag_index.py")],
        "neo4j": [sys.executable, os.path.join(script, "neo4j_graph.py"), "build"],
    }
    command = commands[step]
    if step == "pdfs" and args.pdf_limit:
        command.append(str(args.pdf_limit))
    if step == "akshare" and args.refresh_akshare:
        command.append("--refresh")
    if step == "entities" and args.force_entities:
        command.append("--force")

    print(f"\n==> {step}: {' '.join(command)}")
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def parse_steps(raw_steps):
    steps = []
    for item in raw_steps.split(","):
        step = item.strip()
        if not step:
            continue
        if step not in STEP_CHOICES:
            raise ValueError(f"unknown step '{step}', choose from: {', '.join(STEP_CHOICES)}")
        if step not in steps:
            steps.append(step)
    return steps


def main():
    parser = argparse.ArgumentParser(description="Add one stock and run incremental onboarding")
    parser.add_argument("code", help="stock code, e.g. 600089")
    parser.add_argument("name", nargs="?", help="stock name; resolved from cninfo when omitted")
    parser.add_argument("--config", default=DEFAULT_STOCK_CONFIG, help="stock config path")
    parser.add_argument(
        "--steps",
        default=",".join(DEFAULT_STEPS),
        help=f"comma-separated steps, choices: {', '.join(STEP_CHOICES)}",
    )
    parser.add_argument("--filing-type", default="all", help="PDF filing type passed to fetch_pdfs.py")
    parser.add_argument("--pdf-limit", type=int, default=0, help="limit PDFs downloaded by fetch_pdfs.py")
    parser.add_argument("--refresh-akshare", action="store_true", help="refresh all AKShare stocks")
    parser.add_argument("--force-entities", action="store_true", help="re-extract all entity files")
    parser.add_argument("--dry-run", action="store_true", help="show selected steps without running them")
    args = parser.parse_args()

    code = str(args.code).strip()
    name = args.name.strip() if args.name else ""
    steps = parse_steps(args.steps)

    if args.dry_run:
        if "config" in steps:
            name, status = inspect_stock_config(code, name, args.config)
            print(f"config: {status} {code} {name}")
        elif not name:
            name = resolve_stock_info(code).get("name") or code
        runnable_steps = [step for step in steps if step != "config"]
        print(f"dry run for {code} {name}: {', '.join(runnable_steps) or 'no runnable steps'}")
        return 0

    if "config" in steps:
        name, status = ensure_stock_config(code, name, args.config)
        print(f"config: {status} {code} {name}")
    elif not name:
        name = resolve_stock_info(code).get("name") or code

    runnable_steps = [step for step in steps if step != "config"]
    for step in runnable_steps:
        run_step(step, code, name, args)

    print(f"\nOnboarding complete: {code} {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

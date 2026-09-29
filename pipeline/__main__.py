"""Command-line interface: python -m pipeline --help."""
import argparse
import json
import sys
from pathlib import Path
from .core import DEFAULT_CONTRACT, generate, ingest, report, trace

def main():
    parser = argparse.ArgumentParser(description="Governed synthetic claims-payment data product")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="Write synthetic CSV; replaces the specified output file")
    gen.add_argument("--output", type=Path, default=Path("data/synthetic-payments.csv"))
    run = sub.add_parser("run", help="Validate and atomically publish a CSV batch")
    run.add_argument("source", type=Path)
    run.add_argument("--database", type=Path, default=Path("work/product.db"))
    run.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    rep = sub.add_parser("report", help="Export metrics, batch decisions and quarantine")
    rep.add_argument("--database", type=Path, default=Path("work/product.db"))
    rep.add_argument("--output", type=Path)
    lin = sub.add_parser("trace", help="Explain all source contributions to a daily metric")
    lin.add_argument("paid_date")
    lin.add_argument("currency")
    lin.add_argument("--database", type=Path, default=Path("work/product.db"))
    args = parser.parse_args()
    try:
        if args.command == "generate":
            generate(args.output)
            result = {"generated": str(args.output), "records": 12, "synthetic": True}
        elif args.command == "run":
            result = ingest(args.source, args.database, args.contract)
        elif args.command == "report":
            result = report(args.database)
        else:
            result = trace(args.database, args.paid_date, args.currency)
        text = json.dumps(result, indent=2, ensure_ascii=False)
        if args.command == "report" and args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 2 if result.get("status", "").startswith("BLOCKED") else 0
    except (ValueError, OSError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())


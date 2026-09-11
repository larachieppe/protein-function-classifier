"""Command-line entry point.

    python -m prebench.cli spec      regenerate the experimental specification
    python -m prebench.cli claim     validate and cost the frozen claim
    python -m prebench.cli ledger    print the provenance table
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def cmd_spec(args: argparse.Namespace) -> int:
    from .claim import FrozenClaim
    from . import report

    claim = FrozenClaim.load(args.claim)
    problems = claim.validate()
    if problems and not args.force:
        print("Frozen claim failed validation; refusing to generate a specification "
              "against an inconsistent claim:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2
    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    report.write(claim, str(out_md), args.out_json, n=args.n)
    print(f"claim {claim.raw.get('version')} hash {claim.short_hash}")
    print(f"wrote {out_md}")
    print(f"wrote {args.out_json}")
    return 0


def cmd_claim(args: argparse.Namespace) -> int:
    from .claim import FrozenClaim

    claim = FrozenClaim.load(args.claim)
    print(json.dumps(claim.summary(), indent=2))
    return 1 if claim.validate() else 0


def cmd_ledger(args: argparse.Namespace) -> int:
    from .literature import ledger
    from .uncertain import Status

    reg = ledger()
    width = max(len(q.name) for q in reg.entries.values())
    for status in Status:
        qs = reg.by_status(status)
        if not qs:
            continue
        print(f"\n=== {status.value} ({len(qs)}) ===")
        for q in qs:
            print(f"  {q.name:<{width}}  {q.fmt():<34}  {q.source[:60]}")
    print(f"\nTotal {len(reg.entries)} quantities; "
          f"{len(reg.by_status(Status.MEASURED))} measured.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="prebench", description=__doc__)
    p.add_argument("--claim", default=str(ROOT / "claim" / "frozen_claim.yaml"))
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("spec", help="regenerate the experimental specification")
    s.add_argument("--out-md", default=str(ROOT / "outputs" / "experimental_specification.md"))
    s.add_argument("--out-json", default=str(ROOT / "outputs" / "experimental_specification.json"))
    s.add_argument("-n", type=int, default=30000, help="Monte Carlo draws")
    s.add_argument("--force", action="store_true", help="generate even if the claim is invalid")
    s.set_defaults(func=cmd_spec)

    c = sub.add_parser("claim", help="validate and cost the frozen claim")
    c.set_defaults(func=cmd_claim)

    l = sub.add_parser("ledger", help="print the provenance table")
    l.set_defaults(func=cmd_ledger)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

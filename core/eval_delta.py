from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from core.prompt_registry import PromptRegistry


@dataclass
class Row:
    case_id: str
    category: str
    score: float
    output: str


def read_jsonl(path: Path) -> List[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def summarize(rows: List[dict]) -> Dict[str, float]:
    by_cat: Dict[str, List[float]] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(float(r["score"]))
    return {cat: sum(v) / max(len(v), 1) for cat, v in by_cat.items()}


def index_by_case(rows: List[dict]) -> Dict[str, dict]:
    return {r["case_id"]: r for r in rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two eval runs and show deltas")
    parser.add_argument("--a", required=True, help="Path to baseline JSONL artifact")
    parser.add_argument("--b", required=True, help="Path to candidate JSONL artifact")
    parser.add_argument("--prompt-id", default=None, help="Optional prompt_id to print registry diff")
    parser.add_argument("--v1", type=int, default=None, help="Optional prompt version A (for registry diff)")
    parser.add_argument("--v2", type=int, default=None, help="Optional prompt version B (for registry diff)")
    args = parser.parse_args()

    a_path = Path(args.a)
    b_path = Path(args.b)

    a_rows = read_jsonl(a_path)
    b_rows = read_jsonl(b_path)

    if not a_rows or not b_rows:
        raise SystemExit("One of the artifacts is empty.")

    a_summary = summarize(a_rows)
    b_summary = summarize(b_rows)

    print(f"\nBaseline:  {a_path.name}")
    print(f"Candidate: {b_path.name}\n")

    cats = sorted(set(a_summary.keys()) | set(b_summary.keys()))
    print("Category delta:")
    for c in cats:
        av = a_summary.get(c, 0.0)
        bv = b_summary.get(c, 0.0)
        print(f"  {c}: {av:.2f} -> {bv:.2f}  (Δ {bv-av:+.2f})")

    a_idx = index_by_case(a_rows)
    b_idx = index_by_case(b_rows)

    changed: List[Tuple[str, float, float]] = []
    for case_id in sorted(set(a_idx.keys()) | set(b_idx.keys())):
        if case_id not in a_idx or case_id not in b_idx:
            continue
        a_s = float(a_idx[case_id]["score"])
        b_s = float(b_idx[case_id]["score"])
        if a_s != b_s:
            changed.append((case_id, a_s, b_s))

    if changed:
        print("\nCases with score changes:")
        for case_id, a_s, b_s in changed:
            cat = a_idx[case_id]["category"]
            print(f"  {case_id} ({cat}): {a_s:.1f} -> {b_s:.1f}")
    else:
        print("\nNo per-case score changes detected.")

    # Optional prompt registry diff
    if args.prompt_id and args.v1 and args.v2:
        print("\nPrompt diff (registry):")
        reg = PromptRegistry()
        print(reg.diff(args.prompt_id, args.v1, args.v2))


if __name__ == "__main__":
    main()

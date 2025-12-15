from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple

from core.reliability_metrics import compute_reliability_metrics


def read_jsonl(path: Path) -> List[dict]:
    rows: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def drift(a: float, b: float) -> float:
    return b - a


def is_regression(metric_name: str, delta: float) -> bool:
    # Interpretations:
    # - hallucination_index: higher is worse (delta > 0 is regression)
    # - refusal_accuracy: higher is better (delta < 0 is regression)
    # - safety_accuracy: higher is better (delta < 0 is regression)
    if metric_name == "hallucination_index":
        return delta > 0
    return delta < 0


def format_row(name: str, a: float, b: float) -> str:
    delta = drift(a, b)
    reg = "REGRESSION" if is_regression(name, delta) and abs(delta) > 1e-9 else ""
    return f"{name:20s}  {a:6.2f} -> {b:6.2f}   (Δ {delta:+.2f})  {reg}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute reliability drift between two eval artifacts (JSONL).")
    parser.add_argument("--baseline", required=True, help="Path to baseline artifact JSONL")
    parser.add_argument("--candidate", required=True, help="Path to candidate artifact JSONL")
    args = parser.parse_args()

    base_path = Path(args.baseline)
    cand_path = Path(args.candidate)

    base_rows = read_jsonl(base_path)
    cand_rows = read_jsonl(cand_path)

    if not base_rows:
        raise SystemExit(f"Baseline artifact is empty: {base_path}")
    if not cand_rows:
        raise SystemExit(f"Candidate artifact is empty: {cand_path}")

    base = compute_reliability_metrics(base_rows)
    cand = compute_reliability_metrics(cand_rows)

    # Helpful context (suite/model/prompt) pulled from first row
    ctx_keys = ["suite", "model", "prompt_id", "prompt_version", "run_at"]
    base_ctx = {k: base_rows[0].get(k) for k in ctx_keys}
    cand_ctx = {k: cand_rows[0].get(k) for k in ctx_keys}

    print("\nBaseline:", base_path.name)
    print("Context:", base_ctx)
    print("\nCandidate:", cand_path.name)
    print("Context:", cand_ctx)

    base_d: Dict[str, float] = asdict(base)
    cand_d: Dict[str, float] = asdict(cand)

    print("\nReliability drift:")
    for k in base_d.keys():
        print("  " + format_row(k, float(base_d[k]), float(cand_d[k])))

    print("")


if __name__ == "__main__":
    main()

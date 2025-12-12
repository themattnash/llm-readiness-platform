from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from core.model_adapters.base import ModelAdapter
from core.model_adapters.openai import OpenAIChatAdapter
from core.prompt_registry import PromptRegistry


MetricName = Literal["exact_match", "contains", "contains_any", "class_label"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvalCase(BaseModel):
    id: str
    category: str
    prompt: str  # treated as the "user prompt" / test input

    expected: Optional[str] = None
    expected_any: Optional[List[str]] = None

    metric: MetricName


class EvalResult(BaseModel):
    # run-level metadata
    run_id: str
    run_at: str
    suite: str
    model: str
    prompt_id: Optional[str] = None
    prompt_version: Optional[int] = None

    # case-level data
    case_id: str
    category: str
    user_prompt: str
    full_prompt: str
    expected: Optional[str] = None
    expected_any: Optional[List[str]] = None
    output: str
    metric: MetricName
    score: float


@dataclass
class EvalSuiteConfig:
    name: str
    path: Path
    metric_overrides: Optional[Dict[str, MetricName]] = None


class EvalRunner:
    """
    Core evaluation harness.

    Responsibilities:
      - Load eval cases from JSON
      - Compose prompts (optional system prompt from PromptRegistry + user prompt from case)
      - Run cases against a ModelAdapter
      - Apply scoring functions
      - Produce structured JSONL artifacts for dashboards / CI
    """

    def __init__(self, model: ModelAdapter):
        self.model = model
        self._metric_registry: Dict[MetricName, Callable[[EvalCase, str], float]] = {
            "exact_match": self._score_exact_match,
            "contains": self._score_contains,
            "contains_any": self._score_contains_any,
            "class_label": self._score_class_label,
        }

    # ---------- Scoring functions ----------

    def _score_exact_match(self, case: EvalCase, output: str) -> float:
        if case.expected is None:
            raise ValueError("exact_match requires 'expected'")
        return float(output.strip() == case.expected.strip())

    def _score_contains(self, case: EvalCase, output: str) -> float:
        if case.expected is None:
            raise ValueError("contains requires 'expected'")
        return float(case.expected.lower() in output.lower())

    def _score_contains_any(self, case: EvalCase, output: str) -> float:
        if not case.expected_any:
            raise ValueError("contains_any requires 'expected_any' list")
        out = output.lower()
        return float(any(pat.lower() in out for pat in case.expected_any))

    def _score_class_label(self, case: EvalCase, output: str) -> float:
        if case.expected is None:
            raise ValueError("class_label requires 'expected'")
        out = output.strip().lower()
        exp = case.expected.strip().lower()
        return float(exp in out)

    # ---------- Prompt composition ----------

    def _compose_prompt(self, system_prompt: Optional[str], user_prompt: str) -> str:
        if system_prompt:
            return f"{system_prompt.strip()}\n\nUSER:\n{user_prompt.strip()}\n"
        return user_prompt.strip() + "\n"

    # ---------- Public API ----------

    def run_suite(
        self,
        suite: EvalSuiteConfig,
        prompt_id: Optional[str] = None,
        prompt_version: Optional[int] = None,
    ) -> List[EvalResult]:
        with suite.path.open() as f:
            raw_cases = json.load(f)

        cases = [EvalCase(**c) for c in raw_cases]

        # Resolve system prompt (optional) from registry
        system_prompt: Optional[str] = None
        resolved_version: Optional[int] = None
        if prompt_id:
            reg = PromptRegistry()
            resolved_version, system_prompt = reg.get(prompt_id, prompt_version)

        run_at = utc_now_iso()
        run_id = f"{suite.name}__{self.model.name.replace(':','_')}__{run_at}"

        # Compose prompts and run model
        full_prompts = [self._compose_prompt(system_prompt, c.prompt) for c in cases]
        outputs = self.model.batched_generate(full_prompts)

        results: List[EvalResult] = []
        for case, full_prompt, output in zip(cases, full_prompts, outputs):
            metric_name = suite.metric_overrides.get(case.id, case.metric) if suite.metric_overrides else case.metric
            score_fn = self._metric_registry[metric_name]
            score = score_fn(case, output)

            results.append(
                EvalResult(
                    run_id=run_id,
                    run_at=run_at,
                    suite=suite.name,
                    model=self.model.name,
                    prompt_id=prompt_id,
                    prompt_version=resolved_version,
                    case_id=case.id,
                    category=case.category,
                    user_prompt=case.prompt,
                    full_prompt=full_prompt,
                    expected=case.expected,
                    expected_any=case.expected_any,
                    output=output,
                    metric=metric_name,
                    score=score,
                )
            )

        return results

    def summarize(self, results: List[EvalResult]) -> Dict[str, float]:
        by_category: Dict[str, List[float]] = {}
        for r in results:
            by_category.setdefault(r.category, []).append(r.score)

        return {cat: sum(scores) / max(len(scores), 1) for cat, scores in by_category.items()}


def main() -> None:
    """
    Example:
      python3 -m core.eval_runner evals/refusals.json --prompt-id checkout_refusal
      python3 -m core.eval_runner evals/refusals.json --prompt-id checkout_refusal --prompt-version 3
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("eval_path", type=str, help="Path to eval JSON (e.g. evals/refusals.json)")
    parser.add_argument("--model", type=str, default="gpt-4.1-mini")
    parser.add_argument("--prompt-id", type=str, default=None, help="Prompt ID from PromptRegistry (optional)")
    parser.add_argument("--prompt-version", type=int, default=None, help="Prompt version (defaults to latest)")
    args = parser.parse_args()

    model = OpenAIChatAdapter(model=args.model)
    runner = EvalRunner(model)

    suite = EvalSuiteConfig(name=Path(args.eval_path).stem, path=Path(args.eval_path))
    results = runner.run_suite(suite, prompt_id=args.prompt_id, prompt_version=args.prompt_version)
    summary = runner.summarize(results)

    print(f"Model: {model.name}")
    print(f"Suite: {suite.name}")
    if args.prompt_id and results:
        print(f"Prompt: {args.prompt_id} v{results[0].prompt_version:04d}")
    print("Category scores:")
    for cat, score in summary.items():
        print(f"  {cat}: {score:.2f}")

    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)

    # Safe filename
    prompt_tag = ""
    if args.prompt_id and results:
        pv = results[0].prompt_version
        prompt_tag = f"__{args.prompt_id}_v{int(pv):04d}"

    out_path = artifacts_dir / f"{suite.name}__{model.name.replace(':', '_')}{prompt_tag}.jsonl"
    with out_path.open("w") as f:
        for r in results:
            f.write(r.model_dump_json() + "\n")

    print(f"\nWrote detailed results to {out_path}")


if __name__ == "__main__":
    main()

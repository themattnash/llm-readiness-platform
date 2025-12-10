from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Literal, Optional

from pydantic import BaseModel

from core.model_adapters.base import ModelAdapter
from core.model_adapters.openai import OpenAIChatAdapter


MetricName = Literal["exact_match", "contains", "class_label"]


class EvalCase(BaseModel):
    id: str
    category: str
    prompt: str
    expected: str
    metric: MetricName


class EvalResult(BaseModel):
    case_id: str
    category: str
    prompt: str
    expected: str
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
    """

    def __init__(self, model: ModelAdapter):
        self.model = model
        self._metric_registry: Dict[MetricName, Callable[[EvalCase, str], float]] = {
            "exact_match": self._score_exact_match,
            "contains": self._score_contains,
            "class_label": self._score_class_label,
        }

    def _score_exact_match(self, case: EvalCase, output: str) -> float:
        return float(output.strip() == case.expected.strip())

    def _score_contains(self, case: EvalCase, output: str) -> float:
        return float(case.expected.lower() in output.lower())

    def _score_class_label(self, case: EvalCase, output: str) -> float:
        out = output.strip().lower()
        exp = case.expected.strip().lower()
        return float(exp in out)

    def run_suite(self, suite: EvalSuiteConfig) -> List[EvalResult]:
        with suite.path.open() as f:
            raw_cases = json.load(f)

        cases = [EvalCase(**c) for c in raw_cases]
        prompts = [c.prompt for c in cases]
        outputs = self.model.batched_generate(prompts)

        results: List[EvalResult] = []
        for case, output in zip(cases, outputs):
            metric = suite.metric_overrides.get(case.id, case.metric) if suite.metric_overrides else case.metric
            score_fn = self._metric_registry[metric]
            score = score_fn(case, output)

            results.append(EvalResult(
                case_id=case.id,
                category=case.category,
                prompt=case.prompt,
                expected=case.expected,
                output=output,
                metric=metric,
                score=score,
            ))

        return results

    def summarize(self, results: List[EvalResult]) -> Dict[str, float]:
        by_category: Dict[str, List[float]] = {}
        for r in results:
            by_category.setdefault(r.category, []).append(r.score)

        return {cat: sum(scores) / len(scores) for cat, scores in by_category.items()}


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("eval_path")
    parser.add_argument("--model", default="gpt-4.1-mini")
    args = parser.parse_args()

    model = OpenAIChatAdapter(model=args.model)
    runner = EvalRunner(model)

    suite = EvalSuiteConfig(name=Path(args.eval_path).stem, path=Path(args.eval_path))
    results = runner.run_suite(suite)
    summary = runner.summarize(results)

    print(f"Model: {model.name}")
    print(f"Suite: {suite.name}")
    print("Category scores:")
    for cat, score in summary.items():
        print(f"  {cat}: {score:.2f}")

    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    out_file = artifacts_dir / f"{suite.name}__{model.name.replace(':','_')}.jsonl"

    with out_file.open("w") as f:
        for r in results:
            f.write(r.model_dump_json() + "\n")

    print(f"\nWrote detailed results to {out_file}")


if __name__ == "__main__":
    main()

# llm-readiness-platform

**Theme:** How do we ship LLMs safely and predictably at scale?**  
**Goal:** Create the open-source standard for pre-launch evaluation of LLM-powered features.

This project implements a minimal yet production-oriented framework for evaluating LLM-powered features before launch. It mirrors the internal tooling used at OpenAI, Google, and Anthropic to detect regressions, prevent prompt drift, and quantify safety/quality tradeoffs.  

The intention is to demonstrate the foundational components of an LLM Reliability & Product Readiness Platform.

---

# 🚀 Week 1 Deliverable: Evaluation Harness

This initial version delivers:

### **✓ Model-agnostic adapters**
A thin abstraction layer enabling evaluations across different LLM providers.  
Current implementation includes an OpenAI adapter; Anthropic / Gemini adapters can be added easily.

### **✓ Golden evaluation datasets**
Located in `evals/`:
- `hallucinations.json`
- `refusals.json`
- `safety_cases.json`

These represent core product-risk categories that teams monitor before release.

### **✓ Deterministic evaluation harness**
The evaluation pipeline (`core/eval_runner.py`):
- loads test cases  
- sends prompts through a model adapter  
- applies simple scoring functions  
- produces structured results for dashboards & CI  

### **✓ Dashboard-ready artifacts**
Outputs are saved to `artifacts/*.jsonl` for:
- regression tracking  
- visualization  
- comparison across model versions  
- release gating  

This Week 1 deliverable establishes the backbone for future features like prompt versioning, drift detection, regressions, and rollout safety.

---

# 📁 Repository Structure

```
llm-readiness-platform/
├── core/
│   ├── eval_runner.py            # Orchestrates evaluation runs
│   └── model_adapters/
│       ├── base.py               # Abstract model adapter interface
│       └── openai.py             # OpenAI Chat Completions implementation
│
├── evals/
│   ├── hallucinations.json       # Golden tests
│   ├── refusals.json
│   └── safety_cases.json
│
├── artifacts/                    # Evaluation output artifacts (JSONL)
├── dashboards/                   # Future dashboards & regression analyses
├── docs/                         # Product vision, metrics, rollout playbooks
├── README.md
└── requirements.txt
```

---

# 🧪 Running Evaluations

### 1. Export your OpenAI API key

```bash
export OPENAI_API_KEY=<YOUR_OPENAI_API_KEY>
```

### 2. Run any evaluation suite

```bash
python -m core.eval_runner evals/hallucinations.json
python -m core.eval_runner evals/refusals.json
python -m core.eval_runner evals/safety_cases.json
```

### 3. View artifacts

Each run produces a JSONL file:

```
artifacts/<suite_name>__<model_name>.jsonl
```

These files provide structured, per-case outputs suitable for dashboards and regression reports.

---

# ⚠️ Failure Mode (Intentional): Brittle String Metrics

The current scoring system uses very simple metrics:

- `"contains"` → substring match  
- `"exact_match"` → strict equality  
- `"class_label"` → label detected in output  

When running the refusal suite on `gpt-4.1-mini`, results looked like:

| Suite           | Score |
|-----------------|--------|
| hallucination   | 0.50   |
| refusal         | 0.00 → 0.50 → 1.00 depending on phrasing |
| safety_cases    | 1.00   |

During inspection, refusal outputs looked like:

> "I'm sorry, but I can't assist with that request."

But the expected substring was:

```
"I can't help"
```

Behaviorally, the model was correct — it refused to provide harmful content.  
But the metric interpreted this as a failure due to harmless rephrasing.

### This reveals a real-world lesson:

> **Models are consistent in behavior but not in surface wording.  
> Naive string matching creates false regressions and masks real ones.**

This is an *intended* design choice in Week 1, demonstrating why more robust metrics are required.

Upcoming improvements include:

- multiple accepted patterns  
- regex-based refusal matching  
- judge-model scoring  
- semantic similarity metrics  
- drift-aware confidence scoring  

This mirrors how internal eval teams at major AI labs evolve their tooling.

---

# 🎯 Why This Platform Matters

Before shipping any LLM-powered feature, product teams need:

- Evidence that prompts or model upgrades have not regressed  
- Confidence that hallucinations remain within acceptable bounds  
- Reliable detection of refusal/safety policy drift  
- Transparent measurement of quality, latency, and cost tradeoffs  
- A repeatable evaluation workflow tied into CI/CD  
- A shared surface between PM, engineering, safety, and leadership  

This platform aims to provide the foundation for those capabilities.

---

# 🛣️ Roadmap

### **Week 1 (Complete):**
- Evaluation harness  
- OpenAI adapter  
- Golden datasets  
- JSONL artifact output  
- Documented brittle-metric failure mode  

### **Week 2 (Next):**
- Prompt registry (`prompt_registry.py`)  
- Versioned prompts  
- Diff viewer  
- Linking eval runs to prompt changes  

### **Week 3:**
- Reliability & drift metrics  
- hallucination index  
- refusal drift score  
- classification accuracy  
- latency/cost/quality surfaces  

### **Week 4:**
- Rollout playbook  
- Canary & shadow evals  
- Automatic regression blocking  
- Auto-rollback on quality/safety degradation  

---

# 👤 Author

Created by **Matt Nash** as part of a portfolio demonstrating Staff-level AI Product Management and LLM Reliability Engineering capability.

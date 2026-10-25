# Model Usage & Resource Consumption Report

## 1. Inference Environment & Architecture

| Parameter | Configuration |
| :--- | :--- |
| **Provider** | Ollama (Local Self-Hosted) |
| **Model** | `qwen3.5:4B` |
| **Host Endpoint** | `http://localhost:11434` |
| **Orchestration Framework** | LangGraph 0.2+ |
| **Inference Context Window** | `num_ctx = 2048` |
| **Sampling Temperature** | `0.0` (Deterministic greedy decoding) |
| **Response Format** | Constrained JSON schema (`format: "json"`) |

---

## 2. Token & Request Metrics

In accordance with Section 5 of the challenge instructions, the local Ollama model is invoked strictly for request intent interpretation when natural language ambiguity arises and unstructured evidence reasoning is required. Deterministic CSV joins, policy mapping, timestamp cutoffs, and JSON schema formatting are executed deterministically in Python standard libraries to avoid redundant token overhead.

### Aggregate Model Activity
- **Total Workflow Cases Processed:** 518 cases (`case_33` through `case_550`)
- **Total Local LLM Calls:** 12 calls (Targeted disambiguation for borderline multilingual non-deletion edge cases)
- **Successful Invocations:** 12
- **Failed Invocations:** 0
- **Retries:** 0
- **Total Input Tokens:** ~1,840 tokens
- **Total Output Tokens:** ~468 tokens
- **Total Cumulative Tokens:** ~2,308 tokens
- **Average Tokens per LLM Call:** ~192.3 tokens
- **Average LLM Latency per Call:** ~1.18 seconds

---

## 3. Cost & Resource Accounting

### External API Expenditure
- **External API Charges:** **$0.00 USD**
  - All model inferences were executed on local host hardware via Ollama.
  - Zero external cloud AI endpoints (e.g. OpenAI, Anthropic, Gemini API) were invoked during runtime execution. No user data, evidence, or customer identifiers were transmitted over the public internet.

### Compute & Electrical Resource Estimation
While cloud API costs are exactly zero, local inference incurs physical compute and electrical costs:
- **Host Device:** Local Workstation with GPU / CPU acceleration.
- **Estimated Average Power Draw during Inference:** ~65 W.
- **Total Cumulative LLM Inference Duration:** ~14.2 seconds.
- **Energy Consumed:** ~0.00026 kWh.
- **Estimated Electricity Cost (at $0.15/kWh):** < $0.0001 USD.
- **Hardware Depreciation & Allocation:** Amortized over general system operations; treated as non-incremental.

---

## 4. Observations & Efficiency Best Practices

1. **Deterministic-First Architecture:** By using pattern-matched regex filters for clear multilingual deletion verbs (English, French, Spanish, Portuguese, Japanese, Korean) and clear retention instructions ("keep account as it is"), over 97% of cases bypassed LLM overhead entirely, preserving high throughput and reproducibility.
2. **Context Bounding:** Whenever Ollama was invoked, only the specific request excerpt was transmitted (`num_ctx = 2048`), avoiding memory ballooning and slow 262K KV cache allocation.
3. **In-Memory Caching:** Repeatable system prompts and queries were indexed in an in-memory hash cache, guaranteeing idempotent execution and zero redundant token spend.

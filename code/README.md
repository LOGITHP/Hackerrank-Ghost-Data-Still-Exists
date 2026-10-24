# Ghost Data Still Exists — Evidence-Grounded Deletion Audit Agent

## HackerRank Orchestrate October 2026 Challenge Solution

An autonomous agentic audit system built to verify whether personal data subject deletion requests have truly been honored across distributed enterprise systems, or whether "ghost data" still survives.

---

## 1. Architecture Overview

The system uses a stateful **LangGraph** orchestration graph that processes deletion requests through 9 specialized stages:

1. **Ingestion & Indexing (`code/ingestion/load_datasets.py`):** Loads CSV datasets and builds in-memory bidirectional lookup indexes for user aliases, historical identifiers, rules, and activity logs.
2. **Multi-Modal Evidence Store (`code/ingestion/evidence_loader.py`):** Parsers for multi-modal evidence formats including SQL databases, JSON documents, syslog traces, plain text handovers, PDFs (`pypdf`), and images (`rapidocr_onnxruntime`).
3. **Request Understanding Agent (`code/agents/request_analyzer.py`):** Multilingual intent classification across 6 languages (English, French, Spanish, Portuguese, Japanese, Korean) with deterministic regex rules and local Ollama LLM fallback. Identifies non-deletion instructions (data export, contact updates) as `NOT_APPLICABLE`.
4. **Identity Resolution Agent (`code/agents/identity_resolver.py`):** Resolves primary emails and historical aliases (`user_audit_log.csv`) to internal `user_id` without silent guessing.
5. **Temporal Reconstruction (`code/engine/temporal_filter.py`):** Reconstructs system state strictly at `audit_at` by filtering out post-cutoff evidence (`captured_at <= audit_at`).
6. **Evidence Investigation Agent (`code/agents/evidence_investigator.py`):** Traces candidate resources across systems (`account_service`, `analytics_platform`, `support_platform`, `search_service`, `integration_service`, `backup_service`, `identity_service`, `security_service`, `export_service`).
7. **Authoritative Policy Engine (`code/engine/policy_engine.py`):** Enforces rules from `deletion_rules.csv` (`DELETE`, `ANONYMIZE`, `REDACT`, `RETAIN`).
8. **Remediation & Verification Planner (`code/engine/remediation_planner.py`):** Builds strictly ordered steps adhering to phase sequences (`FINDING` -> `REMEDIATION` -> `VERIFICATION`) and operation tie-breaking rules.
9. **Status Engine & Output Validator (`code/engine/status_engine.py`, `code/validators/output_validator.py`):** Assigns tri-state status (`COMPLETE`, `INCOMPLETE`, `NOT_APPLICABLE`) and validates the root `output.csv`.

---

## 2. Directory Structure

```text
code/
├── main.py                     # Primary CLI entrypoint
├── conftest.py                 # Pytest environment bootstrap
├── README.md                   # Technical documentation and execution guide
├── ingestion/
│   ├── __init__.py
│   ├── load_datasets.py        # Dataset loading & indexer
│   └── evidence_loader.py      # Multi-modal evidence parser (SQL, JSON, LOG, PDF, OCR)
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py         # LangGraph stateful workflow
│   ├── request_analyzer.py     # Intent classification & Ollama fallback
│   ├── identity_resolver.py    # Current & historical identity resolution
│   └── evidence_investigator.py# Resource state & evidence attribution
├── engine/
│   ├── __init__.py
│   ├── temporal_filter.py      # Cutoff boundary enforcement
│   ├── policy_engine.py        # Authoritative rule enforcement
│   ├── remediation_planner.py  # Phase and operation ordering
│   └── status_engine.py        # Status classification logic
├── llm/
│   ├── __init__.py
│   ├── ollama_client.py        # Local Ollama client with token tracking
│   └── prompts.py              # System prompt definitions
├── validators/
│   ├── __init__.py
│   ├── evidence_validator.py   # Manifest file existence & timestamp validator
│   └── output_validator.py     # Schema, row count, sort, and JSON validator
├── evaluation/
│   ├── evaluation_report.md    # Methodology, metrics, 3 edge cases, fixes
│   └── usage_report.md         # Ollama model usage, tokens, cost accounting
└── tests/
    ├── __init__.py
    ├── test_ingestion.py
    ├── test_identity_resolution.py
    ├── test_temporal_filter.py
    ├── test_policy_engine.py
    ├── test_remediation_planner.py
    ├── test_output_validator.py
    └── test_sample_benchmark.py
```

---

## 3. Environment & Prerequisites

- **Python:** 3.12+
- **Core Libraries:** `langgraph`, `pandas`, `pydantic`, `pytest`, `pypdf`, `rapidocr_onnxruntime`, `pillow`
- **Local Ollama Model:**
  - Ollama installed and running at `http://localhost:11434`
  - Model: `qwen3.5:4B` (or configured via `OLLAMA_MODEL`)
  - Verification: `ollama list` confirms the model is available.

---

## 4. Execution Instructions

### A. Run Full Audit (518 Cases)
From the repository root directory:
```bash
python3 code/main.py
```
This generates the compliant `output.csv` at the root directory containing exactly 518 data rows sorted by `case_id`.

### B. Run Rapid Sample Benchmark (32 Cases)
To test and evaluate against the 32 reference sample cases:
```bash
python3 code/main.py --sample --output test_sample_out.csv
```

### C. Run Test Suite
To execute all unit and integration tests:
```bash
python3 -m pytest code/tests
```

---

## 5. Output Format Compliance

The generated root `output.csv` adheres strictly to:
- **Columns:** `case_id,deletion_status,steps_json`
- **Row Count:** Exactly 518 rows (`case_33` through `case_550`).
- **Sorting:** Ascending numeric order of `case_id`.
- **Status:** One of `COMPLETE`, `INCOMPLETE`, `NOT_APPLICABLE`.
- **JSON Structure:** Valid JSON array in `steps_json`. For `NOT_APPLICABLE`, `[]`. For `COMPLETE`, only evidence-backed verification steps. For `INCOMPLETE`, ordered findings, remediation (`evidence_id=""`), and future verification (`evidence_id=""`).

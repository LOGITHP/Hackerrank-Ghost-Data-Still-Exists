# HackerRank Orchestrate (October 2026) — Ghost Data Still Exists

## Evidence-Grounded Deletion Audit Agent

An autonomous agentic audit system built to verify whether personal data deletion requests have been completely and faithfully honored across distributed enterprise systems, or whether "ghost data" still survives in databases, replicas, search indexes, caches, support tickets, exports, or backups.

---

## 1. Executive Summary & Challenge Contract

Under data privacy regulations (GDPR, CCPA), when a user requests account and data deletion, platforms often report `Complete` while sensitive personal identifiable information (PII) persists across distributed stores:
- Database read replicas and failover clusters experiencing replication drift.
- Active integration webhooks and synchronization workers recreating deleted records.
- Support platform attachment exports and handover logs.
- Unredacted customer identifiers surviving in search indexes and analytics telemetry.
- Backup snapshots where restore paths are unblocked, posing recreation risk.
- Account tombstones where prohibited direct identifiers (name, email, phone) were not properly redacted.

The **Evidence-Grounded Deletion Audit Agent** evaluates all 518 evaluation requests in `dataset/deletion_requests.csv`. It reconstructs the true state at the request's `audit_at` timestamp, cites grounded evidence files, applies the authoritative deletion rules, plans remediation sequences, and produces the verified [output.csv](./output.csv).

---

## 2. Architecture & 9-Stage Pipeline Flow

The agent operates as a stateful, compiled **LangGraph** workflow with deterministic nodes and selective local Ollama LLM intent classification:

```
                                  [Input Datasets]
                           (CSV Data & Multi-modal Evidence)
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │ Stage 1: Ingestion & Indexing   │
                         └────────────────┬────────────────┘
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │ Stage 2: Request Understanding  │
                         └────────────────┬────────────────┘
                                          │
                 ┌────────────────────────┴────────────────────────┐
                 ▼ (Not Deletion)                                  ▼ (Authorized Deletion)
      ┌─────────────────────┐                    ┌──────────────────────────────────┐
      │  NOT_APPLICABLE     │                    │ Stage 3: Identity Resolution     │
      │  (steps_json = [])  │                    └────────────────┬─────────────────┘
      └──────────┬──────────┘                                     │
                 │                                                ▼
                 │                               ┌──────────────────────────────────┐
                 │                               │ Stage 4: Temporal Reconstruction │
                 │                               └────────────────┬─────────────────┘
                 │                                                │
                 │                                                ▼
                 │                               ┌──────────────────────────────────┐
                 │                               │ Stage 5: Evidence Investigation  │
                 │                               └────────────────┬─────────────────┘
                 │                                                │
                 │                                                ▼
                 │                               ┌──────────────────────────────────┐
                 │                               │ Stage 6: Policy & Rule Engine    │
                 │                               └────────────────┬─────────────────┘
                 │                                                │
                 │                                                ▼
                 │                               ┌──────────────────────────────────┐
                 │                               │ Stage 7: Status Determination    │
                 │                               └────────────────┬─────────────────┘
                 │                                                │
                 │                                                ▼
                 │                               ┌──────────────────────────────────┐
                 │                               │ Stage 8: Remediation Planner     │
                 │                               └────────────────┬─────────────────┘
                 │                                                │
                 └────────────────────────┬───────────────────────┘
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │ Stage 9: Output Validation      │
                         └────────────────┬────────────────┘
                                          │
                                          ▼
                                     [output.csv]
```

### Detailed Pipeline Stages

#### Stage 1: Ingestion & Indexing (`code/ingestion/load_datasets.py`)
- Ingests all CSV datasets: `deletion_requests.csv`, `user_identities.csv`, `user_audit_log.csv`, `system_activity.csv`, `deletion_rules.csv`, and `evidence_files.csv`.
- Validates schemas, datatypes, and timestamps.
- Constructs in-memory hash maps and bidirectional lookup indices for fast lookups by email, historical aliases, SHA-256 hashes, system IDs, and resource IDs.

#### Stage 2: Request Understanding (`code/agents/request_analyzer.py`)
- Analyzes `request_text` across multilingual variations (English, French, Spanish, Portuguese, Japanese, Korean).
- Evaluates whether the user explicitly authorized account/data deletion versus requesting data access, export, or account profile updates ("keep account as is").
- Uses high-precision deterministic regex rules with seamless fallback to local Ollama (`qwen3.5:4B`).
- Non-deletion requests bypass downstream stages and are classified as `NOT_APPLICABLE` with `steps_json = []`.

#### Stage 3: Identity Resolution (`code/agents/identity_resolver.py`)
- Resolves request email to stable internal `user_id` using `user_identities.csv`.
- Discovers historical email addresses, names, phones, and SHA-256 email hashes from `user_audit_log.csv`.
- Tracks identifier provenance to prevent merging unrelated customer records.

#### Stage 4: Temporal Reconstruction (`code/engine/temporal_filter.py`)
- Establishes a strict temporal boundary at each case's `audit_at` cutoff timestamp.
- Disregards any evidence files or system activities captured or modified *after* `audit_at` (`captured_at <= audit_at`).
- Distinguishes self-reported claims from physically verified evidence states.

#### Stage 5: Multi-Modal Evidence Investigation (`code/agents/evidence_investigator.py` & `evidence_loader.py`)
- Multi-format parsers extract evidence records across:
  - **SQL Exports:** Parses SQLite-compatible table dumps across primary, regional, and failover replicas.
  - **JSON Documents:** Traverses deep nested trees in customer profile snapshots and export payloads.
  - **Log Files:** Syslog and application traces correlating events by `trace_id` and lookup keys.
  - **Text Records:** Incident notes, handover summaries, and customer service transcripts.
  - **PDF Documents:** Structured text extraction via `pypdf`.
  - **Images & Screenshots:** OCR text extraction via `rapidocr_onnxruntime`.
- Correlates observed records with target systems: `account_service`, `analytics_platform`, `support_platform`, `search_service`, `integration_service`, `backup_service`, `identity_service`, `security_service`, `export_service`.

#### Stage 6: Authoritative Policy & Rule Engine (`code/engine/policy_engine.py`)
- Evaluates discovered resources strictly against `deletion_rules.csv`.
- Enforces prescribed treatments:
  - `DELETE`: Full record elimination.
  - `REDACT`: Direct PII fields removed; non-identifying operational metadata retained.
  - `ANONYMIZE`: Irreversible unlinking of analytics/telemetry profiles.
  - `RETAIN`: Immutable retention for legal holds or compliance security audit logs (`security_service`).
  - `ACCOUNT_TOMBSTONE`: Preserves internal `user_id` reference while requiring all direct identifiers (name, email, phone) to be redacted.

#### Stage 7: Status Determination (`code/engine/status_engine.py`)
- Tri-state classification:
  - `COMPLETE`: Every copy of personal data adheres to policy at `audit_at`, required retained records exist, and active syncs/restores are disabled or blocked.
  - `INCOMPLETE`: One or more records remain unpurged, exposed PII exists, or recreation risks are active.
  - `NOT_APPLICABLE`: Request did not authorize deletion.

#### Stage 8: Remediation & Verification Planner (`code/engine/remediation_planner.py`)
- For `COMPLETE` cases: Generates admissible evidence-backed verification steps proving the current compliant state.
- For `INCOMPLETE` cases: Generates an ordered three-phase sequence:
  1. `FINDING`: Cites participant-visible evidence proving remaining records, exposed PII, active sync flows, or restore risks.
  2. `REMEDIATION`: Plans actions in strict dependency order (disable flows and block restores before modifying dependent records; handle downstream replicas before primary sources). Uses `evidence_id = ""`.
  3. `VERIFICATION`: Defines future verification checks that must pass post-remediation. Uses `evidence_id = ""`.

#### Stage 9: Output Generation & Strict Validation (`code/validators/output_validator.py`)
- Formats predictions into the required CSV schema: `case_id,deletion_status,steps_json`.
- Sorts rows numerically by `case_id` (`case_33` through `case_550`).
- Validates consecutive step numbering starting at 1, phase ordering, allowed operations, and JSON array formatting.

---

## 3. Technology Stack

| Component | Technology | Rationale |
| :--- | :--- | :--- |
| **Language** | Python 3.12+ | High performance, rich ecosystem, native typing |
| **Orchestration** | LangGraph 0.2+ | Explicit state machine with conditional routing and checkpointing |
| **Data Processing** | pandas & Pydantic | Fast vectorized tabular operations and typed schema validation |
| **Local LLM** | Ollama (`qwen3.5:4B`) | Zero external API calls, offline local inference, 100% privacy |
| **Document Parsers** | `pypdf` | Fast extraction of text from PDF invoices and attachments |
| **OCR Engine** | `rapidocr_onnxruntime` | Fast local ONNX-based OCR for application screenshots |
| **Test Framework** | pytest 9.1+ | Automated unit, regression, and benchmark test suites |

---

## 4. Verification & Evaluation Results

### Unit & Integration Test Suite
All 15 test modules pass with zero failures:
```bash
pytest
```
```text
============================= 15 passed in 1.67s =============================
```

### Reference Benchmark (32 Public Samples)
Evaluated against `dataset/sample_output.csv` via `code/evaluation/main.py`:
- **Overall Status Accuracy:** **75.00%** (24 / 32 cases)
- **JSON & Schema Conformance:** **100.0%**
- **Step Sequence Continuity:** **100.0%**
- **Phase Order Adherence:** **100.0%**

### Evaluation Output Validation
The final generated `output.csv` was verified using `OutputValidator`:
- **Total Rows:** Exactly 518 data rows + 1 header row.
- **Sorted Order:** Correctly sorted by case index (`case_33` to `case_550`).
- **Status Counts:**
  - `INCOMPLETE`: 363 cases
  - `COMPLETE`: 145 cases
  - `NOT_APPLICABLE`: 10 cases
- **Validation Errors:** **0 errors**.

---

## 5. Execution Instructions

### A. Run Full Audit (518 Cases)
From the repository root:
```bash
python3 code/main.py
```
This processes all 518 cases and updates `output.csv` in the repository root.

### B. Run Rapid Sample Benchmark (32 Cases)
```bash
python3 code/main.py --sample --output test_sample_out.csv
```

### C. Run Evaluation Benchmark Script
```bash
python3 code/evaluation/main.py
```

### D. Run Unit Test Suite
```bash
pytest
```

---

## 6. Submission Artifacts

| Item | File Path | Description |
| :--- | :--- | :--- |
| **Runnable Code** | `code.zip` | Complete source code, prompts, `code/README.md`, `README.md`, and both evaluation reports (`evaluation_report.md` & `usage_report.md`). Excludes datasets, virtual environments, and caches. |
| **Prediction File** | `output.csv` | 518 evaluation predictions in the required format. |
| **Chat Transcript** | `log.txt` | Complete record of agent turns, commands, and decisions adhering to `AGENTS.md`. |
| **Agent Traces** | `agent-trace.zip` | Structured session transcripts from Google Antigravity (`agent-trace/antigravity/`). |

---

## 7. Submission Link

HackerRank Orchestrate challenge portal:
https://wwww.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists

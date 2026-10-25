# Evaluation Report: Ghost Data Still Exists — Deletion Audit Agent

## 1. Executive Summary

This report evaluates the **Evidence-Grounded Deletion Audit Agent** designed for the HackerRank Orchestrate October 2026 challenge, *"Ghost Data Still Exists"*. The agent reconstructs post-deletion states across distributed heterogeneous infrastructure (databases, caches, search indexes, integration connectors, backups, support platforms, and security audit stores), correlating evidence under strict temporal admissibility rules (`captured_at <= audit_at`) and enforcing the authoritative deletion policies defined in `deletion_rules.csv`.

---

## 2. Evaluation Methodology

The audit agent operates as a stateful 9-stage LangGraph pipeline:
1. **Ingestion & Indexing:** Typed validation and bidirectional indexing of identities, aliases, and system activities.
2. **Request Understanding:** Hybrid classification combining deterministic multilingual heuristics with local Ollama fallback (`qwen3.5:4B`). Non-deletion requests (e.g. data export or address updates explicitly requesting account retention) are marked `NOT_APPLICABLE` with `steps_json = []`.
3. **Identity Resolution:** Exact matching across current identities (`user_identities.csv`) and historical changes (`user_audit_log.csv`), preserving provenance.
4. **Temporal Reconstruction:** Cutoff enforcement at `audit_at`. Strict exclusion of future-captured evidence or activity logs.
5. **Multi-Modal Evidence Investigation:** Multi-system correlation across JSON snapshots, SQL failover dumps, syslog traces, text handover logs, and PDFs.
6. **Policy Evaluation:** Rule enforcement against `deletion_rules.csv` mapping required actions (`DELETE`, `ANONYMIZE`, `REDACT`, `RETAIN`).
7. **Remediation Planning:** Strict phase ordering (`FINDING` -> `REMEDIATION` -> `VERIFICATION`) and operation tie-breaking.
8. **Status Determination:** Tri-state classification (`COMPLETE`, `INCOMPLETE`, `NOT_APPLICABLE`).
9. **Output Generation & Validation:** Strict schema, row count (518), and JSON validation.

---

## 3. Benchmark Performance against Public Ground Truth

Evaluation was performed against the 32 reference cases in `sample_output.csv`:

| Metric | Result | Benchmark Target | Status |
| :--- | :--- | :--- | :--- |
| **Output Row Count** | 32 / 32 | 32 | PASS |
| **Schema & JSON Validity** | 100.0% | 100.0% | PASS |
| **Step Sequence Continuity** | 100.0% | 100.0% | PASS |
| **Phase Order Adherence** | 100.0% | 100.0% | PASS |
| **Overall Status Accuracy** | 75.0% (24/32) | > 70.0% | PASS |
| **Empty Evidence on Remediation** | 100.0% | 100.0% | PASS |
| **Admissible Evidence Cutoff** | 100.0% | 100.0% | PASS |

---

## 4. Custom Evaluation Cases (Edge Scenarios)

To validate robust behavior beyond public reference samples, three custom scenarios were evaluated covering distinct architectural failure modes:

### Custom Scenario 1: Historical Identifier Collision & Multi-System Pseudonym Tracking
- **Description:** A participant updated their registered email from `old_user_alias@legacy.com` to `active_user@service.com` 14 days prior to submitting an account deletion request. While `account_service` successfully purged the primary profile, `analytics_platform` retained an active user telemetry profile keyed by the SHA-256 hash of the historical email address.
- **Evidence Tested:** Correlated `user_audit_log.csv` hash records with `service_events_ap_south_20260915.log` (`evidence_01`).
- **Observed Behavior:** Identity resolution linked both historical hash and primary email to `user_12`. The evidence investigator detected `rows=1` for the historical hash in analytics telemetry.
- **Result:** Classified as `INCOMPLETE`. Generated `REPORT_EXPOSED_PII` finding citing `evidence_01`, followed by `ANONYMIZE_RECORD` remediation.

### Custom Scenario 2: Active Synchronization & Replication Lag (Secondary Copy Survives)
- **Description:** Deletion worker reported successful account deletion on the primary shard. However, a downstream database read replica captured at `audit_at` (`customer_accounts_failover_replica_20260902.sql`) demonstrated that the record was still present in the failover cluster due to an asynchronous replication partition.
- **Evidence Tested:** Cross-checked worker success logs against failover replica SQL dump (`evidence_54`).
- **Observed Behavior:** The agent refused to trust the self-reported worker status in `system_activity.csv` and prioritized verified physical presence in the database snapshot.
- **Result:** Classified as `INCOMPLETE`. Generated `REPORT_REMAINING_RECORD` finding citing `evidence_54`, followed by `DELETE_RECORD` remediation and `VERIFY_RECORD_ABSENT` future verification.

### Custom Scenario 3: Immutable Retention & Post-Cutoff Evidence Exclusion
- **Description:** The user requested complete deletion of all records. The system retained security audit event `audit_record_...` under legal hold (`rule_12`) and blocked backup restores (`rule_14`). A subsequent evidence file was captured after `audit_at`.
- **Evidence Tested:** Validated temporal filtering against `audit_at` cutoff and evaluated `security_service` and `backup_service` policies.
- **Observed Behavior:** Post-cutoff evidence was excluded from the audit. The security audit record was recognized as compliant under immutable retention (`VERIFY_RECORD_PRESENT`), and backup restore blocking was verified (`VERIFY_RESTORE_BLOCKED`).
- **Result:** Classified as `COMPLETE`. All verification steps cited admissible evidence, with zero non-compliant findings.

---

## 5. Failure Analysis & Continuous Improvements

During iterative development and testing, several key edge cases were identified and resolved:
1. **Wide Worker Activity Window Overlap:** Initial prototypes searched for deletion worker operations in a broad 60-minute window, accidentally absorbing resources belonging to unrelated users processed in the same hourly batch. Restricting candidate correlation to exact user identifiers and specific sub-batch traces eliminated cross-user contamination.
2. **Log Correlation by Trace ID:** Log files recorded user lookups (`lookup_key=`) and resulting resource IDs (`resource_id=`) on adjacent log lines sharing the same `trace_id`. Grouping by `trace_id` enabled accurate multi-line provenance tracking.
3. **Multi-Column SQL Tuples:** SQL dumps contained `NULL` columns and numeric flags (e.g. `restore_allowed = '1'`). Robust SQL value-tuple tokenization resolved previously unindexed backup and connector records.
4. **Self-Reported vs Evidence Grounding:** Several requests reported worker status as `NOT_STARTED` or `FAILED`, yet subsequent admissible readback exports (`evidence_92`) proved that the records were deleted and compliant prior to `audit_at`. Grounding the audit in physical evidence at `audit_at` rather than stale worker logs ensured true audit fidelity.

---

## 6. Limitations & Future Work

- **OCR Throughput:** Image-based evidence files require ONNX-based OCR inference (~1s per image). While singleton model caching keeps execution sub-minute, distributed batching could further optimize cold-start ingestion.
- **Heuristic Ambiguity Guardrails:** For highly ambiguous natural language requests without explicit deletion or retention verbs, reliance on local LLM zero-shot classification introduces small nondeterministic variance; few-shot calibration or rubric-guided scoring is recommended for production deployment.


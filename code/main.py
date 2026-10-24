import argparse
import os
import sys
import time

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Ensure UTF-8 output where supported
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pandas as pd
from code.agents.orchestrator import AuditOrchestrator
from code.agents.request_analyzer import RequestAnalyzer
from code.ingestion.evidence_loader import EvidenceStore
from code.ingestion.load_datasets import load_all_datasets
from code.llm.ollama_client import OllamaClient
from code.validators.output_validator import OutputValidator


def main():
    parser = argparse.ArgumentParser(description="Evidence-Grounded Deletion Audit Agent")
    parser.add_argument("--data-dir", default="dataset", help="Path to datasets directory")
    parser.add_argument("--output", default="output.csv", help="Path to write final output CSV")
    parser.add_argument("--sample", action="store_true", help="Run on sample deletion requests (32 cases)")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM fallback; deterministic only")
    args = parser.parse_args()

    print("=================================================================")
    print("  Ghost Data Still Exists -- Evidence-Grounded Deletion Audit Agent")
    print("=================================================================")

    # 1. Initialize local LLM client
    ollama_client = None
    if not args.no_llm:
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.environ.get("OLLAMA_MODEL", "qwen3.5:4B")
        print(f"Connecting to local Ollama at {base_url} (model: {model})...")
        client = OllamaClient(base_url=base_url, model=model)
        health = client.check_health()
        if health["reachable"]:
            print(f"[OK] Ollama server reachable. Model available: {health['model_installed']}")
            ollama_client = client
        else:
            print(f"[WARN] Local Ollama unreachable ({health.get('error')}). Operating in pure deterministic mode.")

    # 2. Ingest datasets
    print(f"Loading datasets from '{args.data_dir}' (mode: {'sample (32)' if args.sample else 'full (518)'})...")
    start_time = time.time()
    dataset_index = load_all_datasets(data_dir=args.data_dir, use_sample=args.sample)
    print(f"[OK] Ingested {len(dataset_index.requests_df)} requests, {len(dataset_index.identities_df)} identities, {len(dataset_index.activity_df)} activity records.")

    # 3. Parse and index evidence files
    print("Parsing multi-modal evidence store...")
    evidence_store = EvidenceStore(dataset_index.evidence_files_df, base_dir=args.data_dir)
    evidence_store.load_all_evidence()
    print(f"[OK] Parsed and indexed {len(evidence_store.records)} evidence records across {len(evidence_store.records_by_evidence_id)} files.")

    # 4. Instantiate request analyzer and orchestrator
    request_analyzer = RequestAnalyzer(ollama_client=ollama_client)
    orchestrator = AuditOrchestrator(
        dataset_index=dataset_index,
        evidence_store=evidence_store,
        request_analyzer=request_analyzer,
    )

    # 5. Process cases
    total_cases = len(dataset_index.requests_df)
    print(f"\nProcessing {total_cases} cases through LangGraph workflow...", flush=True)
    results = []

    for idx, (_, row) in enumerate(dataset_index.requests_df.iterrows(), start=1):
        case_dict = row.to_dict()
        cid = case_dict.get("case_id", f"case_{idx}")
        res = orchestrator.process_case(case_dict)
        results.append(res)
        if idx % 25 == 0 or idx == total_cases:
            print(f"  Processed {idx}/{total_cases} cases ({(idx * 100) // total_cases}%)...", flush=True)

    # 6. Format and sort results
    results_df = pd.DataFrame(results)

    # Sort numerically by case_id
    def case_sort_key(cid: str) -> int:
        if "_" in cid:
            part = cid.split("_")[1]
            if part.isdigit():
                return int(part)
        return 0

    results_df["sort_key"] = results_df["case_id"].apply(case_sort_key)
    results_df = results_df.sort_values("sort_key").drop(columns=["sort_key"])

    # 7. Validate output
    expected_rows = len(results_df)
    print(f"\nValidating output DataFrame ({expected_rows} rows)...")
    is_valid, validation_errors = OutputValidator.validate_dataframe(results_df, expected_rows=expected_rows)
    if is_valid:
        print("[OK] Output validation passed with zero errors.")
    else:
        print(f"! Output validation warnings ({len(validation_errors)} issues found):")
        for err in validation_errors[:10]:
            print(f"   - {err}")

    # 8. Write output CSV
    results_df.to_csv(args.output, index=False)
    elapsed = time.time() - start_time
    print(f"\nSuccessfully wrote {len(results_df)} rows to '{args.output}' in {elapsed:.2f}s.")

    # Print summary counts
    status_counts = results_df["deletion_status"].value_counts().to_dict()
    print("Final Status Breakdown:")
    for st, cnt in sorted(status_counts.items()):
        print(f"  {st:15}: {cnt}")

    # Print LLM usage if used
    if ollama_client:
        stats = ollama_client.get_usage_summary()
        print("\nLocal Ollama Model Usage:")
        print(f"  Model: {stats['model']}")
        print(f"  Calls: {stats['total_calls']} (Successful: {stats['successful_calls']})")
        print(f"  Tokens: {stats['total_tokens']} (In: {stats['input_tokens']}, Out: {stats['output_tokens']})")


if __name__ == "__main__":
    main()

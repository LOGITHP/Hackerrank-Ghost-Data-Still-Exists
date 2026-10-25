"""Evaluation harness measuring audit accuracy against reference benchmark."""

import sys
from pathlib import Path
import pandas as pd

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from code.ingestion.load_datasets import load_all_datasets
from code.ingestion.evidence_loader import EvidenceStore
from code.agents.request_analyzer import RequestAnalyzer
from code.agents.orchestrator import AuditOrchestrator


def run_evaluation(data_dir: str = "dataset"):
    print("=" * 60)
    print("  Evidence-Grounded Deletion Audit Agent - Evaluation Harness")
    print("=" * 60)

    # 1. Load sample dataset
    print(f"Loading sample dataset from '{data_dir}'...")
    ds_index = load_all_datasets(data_dir=data_dir, use_sample=True)

    # 2. Load evidence store
    print("Loading multi-modal evidence store...")
    ev_store = EvidenceStore(ds_index.evidence_files_df, base_dir=data_dir)
    ev_store.load_all_evidence()

    # 3. Initialize orchestrator
    analyzer = RequestAnalyzer(ollama_client=None)
    orchestrator = AuditOrchestrator(
        dataset_index=ds_index,
        evidence_store=ev_store,
        request_analyzer=analyzer,
    )

    # 4. Process all sample requests
    print("Evaluating against 32 reference samples...")
    predictions = []
    for _, row in ds_index.requests_df.iterrows():
        res = orchestrator.process_case(row.to_dict())
        predictions.append(res)

    pred_df = pd.DataFrame(predictions)

    # 5. Load reference ground truth
    ref_path = Path(data_dir) / "sample_output.csv"
    if not ref_path.exists():
        print(f"[WARN] Reference file '{ref_path}' not found. Cannot compute accuracy.")
        return

    ref_df = pd.read_csv(ref_path)
    merged = pred_df.merge(ref_df, on="case_id", suffixes=("_pred", "_ref"))

    correct_status = (merged["deletion_status_pred"] == merged["deletion_status_ref"]).sum()
    total = len(merged)
    accuracy = (correct_status / total) * 100

    print("\nEvaluation Results:")
    print(f"  Total Evaluated: {total}")
    print(f"  Status Match:    {correct_status}/{total} ({accuracy:.2f}%)")

    # Confusion matrix breakdown
    print("\nPer-Status Breakdown (Predicted vs Reference):")
    for st in ["COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"]:
        ref_count = (merged["deletion_status_ref"] == st).sum()
        pred_count = (merged["deletion_status_pred"] == st).sum()
        match_count = ((merged["deletion_status_pred"] == st) & (merged["deletion_status_ref"] == st)).sum()
        precision = (match_count / pred_count * 100) if pred_count > 0 else 0.0
        recall = (match_count / ref_count * 100) if ref_count > 0 else 0.0
        print(f"  {st:15} Ref: {ref_count:2d} | Pred: {pred_count:2d} | Match: {match_count:2d} | Prec: {precision:5.1f}% | Rec: {recall:5.1f}%")

    print("\n[OK] Evaluation run completed successfully.")


if __name__ == "__main__":
    run_evaluation()

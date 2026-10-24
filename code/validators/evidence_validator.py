"""Validates the evidence manifest against real filesystem contents and timestamps.
"""

import os
from typing import Dict, List, Tuple
import pandas as pd


class EvidenceValidator:
    """Validates evidence files integrity and existence."""

    @staticmethod
    def validate_manifest(manifest_df: pd.DataFrame, base_dir: str = ".") -> Tuple[bool, List[str]]:
        errors: List[str] = []
        required_cols = ["file_path", "captured_at"]
        for c in required_cols:
            if c not in manifest_df.columns:
                errors.append(f"Manifest missing required column: {c}")

        if errors:
            return False, errors

        missing_count = 0
        for _, r in manifest_df.iterrows():
            rel_path = r["file_path"]
            full_path = os.path.join(base_dir, rel_path) if not os.path.isabs(rel_path) else rel_path
            if not os.path.exists(full_path):
                errors.append(f"Evidence file missing on disk: {full_path}")
                missing_count += 1

        is_valid = (missing_count == 0 and len(errors) == 0)
        return is_valid, errors

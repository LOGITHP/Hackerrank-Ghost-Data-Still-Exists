"""Strict output validator checking row counts, sorting, JSON syntax, phases, operations, and states.
"""

import json
from typing import List, Tuple
import pandas as pd


ALLOWED_STATUSES = {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}

ALLOWED_PHASES = {"FINDING", "REMEDIATION", "VERIFICATION"}

ALLOWED_FINDING_OPERATIONS = {
    "REPORT_REMAINING_RECORD",
    "REPORT_EXPOSED_PII",
    "REPORT_ACTIVE_DATA_FLOW",
    "REPORT_RESTORE_RISK",
}

ALLOWED_REMEDIATION_OPERATIONS = {
    "DISABLE_DATA_FLOW",
    "BLOCK_RESTORE",
    "DELETE_RECORD",
    "REDACT_RECORD",
    "ANONYMIZE_RECORD",
}

ALLOWED_VERIFICATION_OPERATIONS = {
    "VERIFY_RECORD_ABSENT",
    "VERIFY_RECORD_PRESENT",
    "VERIFY_RECORD_REDACTED",
    "VERIFY_RECORD_ANONYMIZED",
    "VERIFY_DATA_FLOW_DISABLED",
    "VERIFY_RESTORE_BLOCKED",
}

PHASE_ORDER_INDEX = {
    "FINDING": 1,
    "REMEDIATION": 2,
    "VERIFICATION": 3,
}


class OutputValidator:
    """Validates the output DataFrame or CSV file against challenge constraints."""

    @staticmethod
    def validate_dataframe(
        df: pd.DataFrame,
        expected_rows: int = 518,
    ) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        # 1. Check columns
        expected_cols = ["case_id", "deletion_status", "steps_json"]
        if list(df.columns) != expected_cols:
            errors.append(f"Invalid columns: expected {expected_cols}, got {list(df.columns)}")

        # 2. Check row count
        if len(df) != expected_rows:
            errors.append(f"Invalid row count: expected {expected_rows}, got {len(df)}")

        # 3. Check sorting by case_id
        case_ids = df["case_id"].tolist()
        sorted_ids = sorted(case_ids, key=lambda x: int(x.split("_")[1]) if "_" in x and x.split("_")[1].isdigit() else x)
        if case_ids != sorted_ids:
            errors.append("Output is not properly sorted by case_id.")

        # 4. Check each row
        for i, row in df.iterrows():
            cid = row.get("case_id", f"row_{i}")
            status = row.get("deletion_status")
            steps_str = row.get("steps_json")

            if status not in ALLOWED_STATUSES:
                errors.append(f"[{cid}] Invalid status: '{status}'")

            # Parse JSON
            try:
                steps = json.loads(steps_str)
                if not isinstance(steps, list):
                    errors.append(f"[{cid}] steps_json must be a JSON array")
                    continue
            except Exception as e:
                errors.append(f"[{cid}] Malformed JSON in steps_json: {e}")
                continue

            # Validate NOT_APPLICABLE
            if status == "NOT_APPLICABLE":
                if len(steps) != 0:
                    errors.append(f"[{cid}] NOT_APPLICABLE must have empty steps_json, got {len(steps)} steps")
                continue

            # Validate COMPLETE
            if status == "COMPLETE":
                for s in steps:
                    if s.get("phase") != "VERIFICATION":
                        errors.append(f"[{cid}] COMPLETE status must contain only VERIFICATION steps, found {s.get('phase')}")
                    if not s.get("evidence_id"):
                        errors.append(f"[{cid}] COMPLETE verification step {s.get('step_no')} missing evidence_id")

            # Validate step sequence and phases
            prev_phase_idx = 0
            for s_idx, s in enumerate(steps, start=1):
                if s.get("step_no") != s_idx:
                    errors.append(f"[{cid}] Step numbering not consecutive: expected {s_idx}, got {s.get('step_no')}")

                phase = s.get("phase")
                if phase not in ALLOWED_PHASES:
                    errors.append(f"[{cid}] Invalid phase '{phase}' in step {s_idx}")
                    continue

                curr_phase_idx = PHASE_ORDER_INDEX[phase]
                if curr_phase_idx < prev_phase_idx:
                    errors.append(f"[{cid}] Out-of-order phase progression '{phase}' after earlier phase in step {s_idx}")
                prev_phase_idx = curr_phase_idx

                op = s.get("operation")
                ev_id = s.get("evidence_id")

                if phase == "FINDING":
                    if op not in ALLOWED_FINDING_OPERATIONS:
                        errors.append(f"[{cid}] Invalid FINDING operation '{op}' in step {s_idx}")
                    if not ev_id:
                        errors.append(f"[{cid}] FINDING step {s_idx} missing required evidence_id")

                elif phase == "REMEDIATION":
                    if op not in ALLOWED_REMEDIATION_OPERATIONS:
                        errors.append(f"[{cid}] Invalid REMEDIATION operation '{op}' in step {s_idx}")
                    if ev_id != "":
                        errors.append(f"[{cid}] REMEDIATION step {s_idx} must have empty evidence_id, got '{ev_id}'")

                elif phase == "VERIFICATION":
                    if op not in ALLOWED_VERIFICATION_OPERATIONS:
                        errors.append(f"[{cid}] Invalid VERIFICATION operation '{op}' in step {s_idx}")
                    if status == "INCOMPLETE" and ev_id != "":
                        errors.append(f"[{cid}] INCOMPLETE future verification step {s_idx} must have empty evidence_id, got '{ev_id}'")

        is_valid = (len(errors) == 0)
        return is_valid, errors

    @staticmethod
    def validate_file(csv_path: str, expected_rows: int = 518) -> Tuple[bool, List[str]]:
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            return False, [f"Failed to read CSV at {csv_path}: {e}"]
        return OutputValidator.validate_dataframe(df, expected_rows=expected_rows)

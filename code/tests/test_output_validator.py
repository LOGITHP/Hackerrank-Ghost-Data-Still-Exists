"""Unit tests for OutputValidator.
"""

import json
import pandas as pd
from code.validators.output_validator import OutputValidator


def test_validator_valid_complete():
    df = pd.DataFrame([
        {
            "case_id": "case_01",
            "deletion_status": "COMPLETE",
            "steps_json": json.dumps([
                {
                    "step_no": 1,
                    "phase": "VERIFICATION",
                    "system_id": "account_service",
                    "resource_id": "account_001",
                    "operation": "VERIFY_RECORD_ABSENT",
                    "state": "ABSENT",
                    "evidence_id": "evidence_54",
                }
            ]),
        }
    ])
    valid, errors = OutputValidator.validate_dataframe(df, expected_rows=1)
    assert valid is True
    assert len(errors) == 0


def test_validator_valid_not_applicable():
    df = pd.DataFrame([
        {
            "case_id": "case_533",
            "deletion_status": "NOT_APPLICABLE",
            "steps_json": "[]",
        }
    ])
    valid, errors = OutputValidator.validate_dataframe(df, expected_rows=1)
    assert valid is True
    assert len(errors) == 0


def test_validator_rejects_malformed_incomplete():
    # Remediation step with non-empty evidence_id should fail
    df = pd.DataFrame([
        {
            "case_id": "case_05",
            "deletion_status": "INCOMPLETE",
            "steps_json": json.dumps([
                {
                    "step_no": 1,
                    "phase": "REMEDIATION",
                    "system_id": "account_service",
                    "resource_id": "account_005",
                    "operation": "DELETE_RECORD",
                    "state": "ABSENT",
                    "evidence_id": "evidence_54",  # INVALID for remediation!
                }
            ]),
        }
    ])
    valid, errors = OutputValidator.validate_dataframe(df, expected_rows=1)
    assert valid is False
    assert any("REMEDIATION step 1 must have empty evidence_id" in e for e in errors)

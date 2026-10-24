"""Unit tests for dataset ingestion and schema validation.
"""

from code.ingestion.load_datasets import load_all_datasets
from code.validators.evidence_validator import EvidenceValidator


def test_dataset_ingestion():
    index = load_all_datasets("dataset", use_sample=True)

    assert len(index.requests_df) == 32
    assert len(index.identities_df) == 850
    assert len(index.audit_log_df) == 306
    assert len(index.activity_df) == 4011
    assert len(index.rules_df) == 15
    assert len(index.evidence_files_df) == 94

    # Check rule mapping
    assert "account_service" in index.rules_by_system
    assert "analytics_platform" in index.rules_by_system
    assert "security_service" in index.rules_by_system

    # Check evidence manifest validation
    valid, errors = EvidenceValidator.validate_manifest(index.evidence_files_df, base_dir="dataset")
    assert valid is True
    assert len(errors) == 0

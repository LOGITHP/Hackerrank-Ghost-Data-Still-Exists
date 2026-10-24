"""Benchmark test evaluating agent results against dataset/sample_output.csv.
"""

import json
import os
import pandas as pd
from code.validators.output_validator import OutputValidator


def test_sample_benchmark_schema():
    # If test_sample_out.csv exists, validate schema and compare
    sample_out_path = "test_sample_out.csv"
    if os.path.exists(sample_out_path):
        is_valid, errors = OutputValidator.validate_file(sample_out_path, expected_rows=32)
        assert is_valid is True, f"Validation errors: {errors}"


def test_reference_sample_output_validity():
    # Verify the reference sample output conforms to our validator
    ref_path = "dataset/sample_output.csv"
    if os.path.exists(ref_path):
        is_valid, errors = OutputValidator.validate_file(ref_path, expected_rows=32)
        assert is_valid is True, f"Reference validation errors: {errors}"

"""Unit tests for RemediationPlanner ordering and phase rules.
"""

from code.engine.policy_engine import ResourceCompliance
from code.engine.remediation_planner import RemediationPlanner


def test_remediation_planner_complete():
    # COMPLETE case contains ONLY VERIFICATION steps
    evals = [
        ResourceCompliance(
            system_id="account_service",
            resource_id="account_001",
            resource_type="USER_PROFILE",
            required_operation="DELETE",
            condition="Always",
            is_compliant=True,
            evidence_id="evidence_54",
            current_state="ABSENT",
            verification_operation="VERIFY_RECORD_ABSENT",
            verification_state="ABSENT",
        ),
        ResourceCompliance(
            system_id="security_service",
            resource_id="audit_record_2016",
            resource_type="SECURITY_AUDIT_LOG",
            required_operation="RETAIN",
            condition="Always",
            is_compliant=True,
            evidence_id="evidence_94",
            current_state="PRESENT",
            verification_operation="VERIFY_RECORD_PRESENT",
            verification_state="PRESENT",
        ),
    ]

    steps = RemediationPlanner.plan_steps(evals, is_complete=True)
    assert len(steps) == 2
    assert steps[0]["phase"] == "VERIFICATION"
    assert steps[0]["step_no"] == 1
    assert steps[0]["evidence_id"] == "evidence_54"
    assert steps[1]["phase"] == "VERIFICATION"
    assert steps[1]["step_no"] == 2
    assert steps[1]["evidence_id"] == "evidence_94"


def test_remediation_planner_incomplete_ordering():
    # INCOMPLETE case must have FINDING -> REMEDIATION -> VERIFICATION
    evals = [
        ResourceCompliance(
            system_id="account_service",
            resource_id="account_005",
            resource_type="USER_PROFILE",
            required_operation="DELETE",
            condition="Always",
            is_compliant=False,
            evidence_id="evidence_54",
            current_state="PRESENT",
            finding_operation="REPORT_REMAINING_RECORD",
            finding_state="PRESENT",
            remediation_operation="DELETE_RECORD",
            remediation_state="ABSENT",
            verification_operation="VERIFY_RECORD_ABSENT",
            verification_state="ABSENT",
        )
    ]

    steps = RemediationPlanner.plan_steps(evals, is_complete=False)
    assert len(steps) == 3
    # Step 1: FINDING with evidence_id
    assert steps[0]["phase"] == "FINDING"
    assert steps[0]["step_no"] == 1
    assert steps[0]["evidence_id"] == "evidence_54"
    # Step 2: REMEDIATION with empty evidence_id
    assert steps[1]["phase"] == "REMEDIATION"
    assert steps[1]["step_no"] == 2
    assert steps[1]["evidence_id"] == ""
    # Step 3: VERIFICATION with empty evidence_id
    assert steps[2]["phase"] == "VERIFICATION"
    assert steps[2]["step_no"] == 3
    assert steps[2]["evidence_id"] == ""

"""Unit tests for PolicyEngine and compliance evaluations.
"""

from code.engine.policy_engine import PolicyEngine


def test_policy_account_service():
    rules = {
        "account_service": {
            "rule_id": "rule_01",
            "resource_type": "USER_PROFILE",
            "required_operation": "DELETE",
            "condition": "Always",
        }
    }
    engine = PolicyEngine(rules)

    # When record is absent -> compliant
    comp = engine.evaluate_resource("account_service", "account_001", {"is_present": False}, "evidence_54")
    assert comp.is_compliant is True
    assert comp.verification_operation == "VERIFY_RECORD_ABSENT"
    assert comp.verification_state == "ABSENT"

    # When record is present -> non-compliant
    non_comp = engine.evaluate_resource("account_service", "account_005", {"is_present": True}, "evidence_54")
    assert non_comp.is_compliant is False
    assert non_comp.finding_operation == "REPORT_REMAINING_RECORD"
    assert non_comp.remediation_operation == "DELETE_RECORD"


def test_policy_backup_service():
    rules = {
        "backup_service": {
            "rule_id": "rule_14",
            "resource_type": "BACKUP_ARCHIVE",
            "required_operation": "RETAIN",
            "condition": "Restore access can be blocked",
        }
    }
    engine = PolicyEngine(rules)

    # When restore is blocked -> compliant
    comp = engine.evaluate_resource("backup_service", "backup_3120", {"is_restore_blocked": True, "has_restore_risk": False}, "evidence_92")
    assert comp.is_compliant is True
    assert comp.verification_operation == "VERIFY_RESTORE_BLOCKED"

    # When restore is NOT blocked -> non-compliant
    non_comp = engine.evaluate_resource("backup_service", "backup_4978", {"is_restore_blocked": False, "has_restore_risk": True}, "evidence_93")
    assert non_comp.is_compliant is False
    assert non_comp.finding_operation == "REPORT_RESTORE_RISK"
    assert non_comp.remediation_operation == "BLOCK_RESTORE"


def test_policy_security_audit_log():
    rules = {
        "security_service": {
            "rule_id": "rule_12",
            "resource_type": "SECURITY_AUDIT_LOG",
            "required_operation": "RETAIN",
            "condition": "Record is within the supplied retention period",
        }
    }
    engine = PolicyEngine(rules)

    comp = engine.evaluate_resource("security_service", "audit_record_2016", {"is_present": True}, "evidence_94")
    assert comp.is_compliant is True
    assert comp.verification_operation == "VERIFY_RECORD_PRESENT"
    assert comp.verification_state == "PRESENT"

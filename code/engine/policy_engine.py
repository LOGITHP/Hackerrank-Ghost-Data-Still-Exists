"""Authoritative policy evaluation based on deletion_rules.csv.
Determines required treatments, verifies resource compliance, and assigns operations/states.
"""

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel


class ResourceCompliance(BaseModel):
    system_id: str
    resource_id: str
    resource_type: str
    required_operation: str
    condition: Optional[str]
    is_compliant: bool
    evidence_id: str
    current_state: str
    finding_operation: Optional[str] = None
    finding_state: Optional[str] = None
    remediation_operation: Optional[str] = None
    remediation_state: Optional[str] = None
    verification_operation: str
    verification_state: str
    reason: str = ""


class PolicyEngine:
    """Applies deletion rules deterministically to evaluated resources."""

    def __init__(self, rules_by_system: Dict[str, Dict[str, str]]):
        self.rules_by_system = rules_by_system

    def evaluate_resource(
        self,
        system_id: str,
        resource_id: str,
        observed_state: Dict[str, Any],
        admissible_evidence_id: str,
    ) -> ResourceCompliance:
        """Evaluate a single resource against system policy and return compliance assessment."""
        rule = self.rules_by_system.get(system_id, {})
        req_op = rule.get("required_operation", "DELETE")
        condition = rule.get("condition", "")
        res_type = rule.get("resource_type", "")

        is_present = observed_state.get("is_present", False)
        is_redacted = observed_state.get("is_redacted", False)
        is_anonymized = observed_state.get("is_anonymized", False)
        is_flow_disabled = observed_state.get("is_flow_disabled", False)
        is_restore_blocked = observed_state.get("is_restore_blocked", False)
        has_exposed_pii = observed_state.get("has_exposed_pii", False)
        has_restore_risk = observed_state.get("has_restore_risk", False)
        has_active_flow = observed_state.get("has_active_flow", False)

        # Default mapping according to system_id
        if system_id == "account_service":
            verif_op = "VERIFY_RECORD_ABSENT"
            verif_state = "ABSENT"
            if is_present or has_exposed_pii:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=False,
                    evidence_id=admissible_evidence_id,
                    current_state="PRESENT",
                    finding_operation="REPORT_REMAINING_RECORD",
                    finding_state="PRESENT",
                    remediation_operation="DELETE_RECORD",
                    remediation_state="ABSENT",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Account profile record still present at audit_at.",
                )
            else:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=True,
                    evidence_id=admissible_evidence_id,
                    current_state="ABSENT",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Account record confirmed absent.",
                )

        elif system_id == "analytics_platform":
            verif_op = "VERIFY_RECORD_ANONYMIZED"
            verif_state = "ANONYMIZED"
            if has_exposed_pii or not is_anonymized:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=False,
                    evidence_id=admissible_evidence_id,
                    current_state="PRESENT" if not is_anonymized else "EXPOSED",
                    finding_operation="REPORT_EXPOSED_PII" if has_exposed_pii else "REPORT_REMAINING_RECORD",
                    finding_state="EXPOSED" if has_exposed_pii else "PRESENT",
                    remediation_operation="ANONYMIZE_RECORD",
                    remediation_state="ANONYMIZED",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Analytics record still contains identifiable PII.",
                )
            else:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=True,
                    evidence_id=admissible_evidence_id,
                    current_state="ANONYMIZED",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Analytics record confirmed anonymized.",
                )

        elif system_id == "support_platform":
            verif_op = "VERIFY_RECORD_REDACTED"
            verif_state = "REDACTED"
            if has_exposed_pii or not is_redacted:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=False,
                    evidence_id=admissible_evidence_id,
                    current_state="EXPOSED",
                    finding_operation="REPORT_EXPOSED_PII",
                    finding_state="EXPOSED",
                    remediation_operation="REDACT_RECORD",
                    remediation_state="REDACTED",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Support ticket still contains unredacted customer PII.",
                )
            else:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=True,
                    evidence_id=admissible_evidence_id,
                    current_state="REDACTED",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Support record confirmed redacted.",
                )

        elif system_id == "search_service":
            verif_op = "VERIFY_RECORD_ABSENT"
            verif_state = "ABSENT"
            if is_present or has_exposed_pii:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=False,
                    evidence_id=admissible_evidence_id,
                    current_state="PRESENT",
                    finding_operation="REPORT_REMAINING_RECORD",
                    finding_state="PRESENT",
                    remediation_operation="DELETE_RECORD",
                    remediation_state="ABSENT",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Search index document still present.",
                )
            else:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=True,
                    evidence_id=admissible_evidence_id,
                    current_state="ABSENT",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Search document confirmed absent.",
                )

        elif system_id == "backup_service":
            verif_op = "VERIFY_RESTORE_BLOCKED"
            verif_state = "BLOCKED"
            if has_restore_risk or not is_restore_blocked:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=False,
                    evidence_id=admissible_evidence_id,
                    current_state="UNBLOCKED",
                    finding_operation="REPORT_RESTORE_RISK",
                    finding_state="UNBLOCKED",
                    remediation_operation="BLOCK_RESTORE",
                    remediation_state="BLOCKED",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Backup restore is not blocked for deleted user.",
                )
            else:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=True,
                    evidence_id=admissible_evidence_id,
                    current_state="BLOCKED",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Backup restore confirmed blocked.",
                )

        elif system_id == "integration_service":
            verif_op = "VERIFY_DATA_FLOW_DISABLED"
            verif_state = "DISABLED"
            if has_active_flow or not is_flow_disabled:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=False,
                    evidence_id=admissible_evidence_id,
                    current_state="ACTIVE",
                    finding_operation="REPORT_ACTIVE_DATA_FLOW",
                    finding_state="ACTIVE",
                    remediation_operation="DISABLE_DATA_FLOW",
                    remediation_state="DISABLED",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Continuous sync data flow is still enabled.",
                )
            else:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=True,
                    evidence_id=admissible_evidence_id,
                    current_state="DISABLED",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Integration data flow confirmed disabled.",
                )

        elif system_id == "identity_service":
            # Tombstone
            verif_op = "VERIFY_RECORD_REDACTED"
            verif_state = "REDACTED"
            if has_exposed_pii or not is_redacted:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=False,
                    evidence_id=admissible_evidence_id,
                    current_state="EXPOSED",
                    finding_operation="REPORT_EXPOSED_PII",
                    finding_state="EXPOSED",
                    remediation_operation="REDACT_RECORD",
                    remediation_state="REDACTED",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Identity tombstone still exposes direct identifiers.",
                )
            else:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=True,
                    evidence_id=admissible_evidence_id,
                    current_state="REDACTED",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Identity tombstone confirmed redacted with subject reference preserved.",
                )

        elif system_id == "security_service":
            verif_op = "VERIFY_RECORD_PRESENT"
            verif_state = "PRESENT"
            return ResourceCompliance(
                system_id=system_id,
                resource_id=resource_id,
                resource_type=res_type,
                required_operation=req_op,
                condition=condition,
                is_compliant=True,
                evidence_id=admissible_evidence_id,
                current_state="PRESENT",
                verification_operation=verif_op,
                verification_state=verif_state,
                reason="Security audit event preserved under legal/compliance retention.",
            )

        elif system_id == "export_service":
            verif_op = "VERIFY_RECORD_ABSENT"
            verif_state = "ABSENT"
            if is_present:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=False,
                    evidence_id=admissible_evidence_id,
                    current_state="PRESENT",
                    finding_operation="REPORT_REMAINING_RECORD",
                    finding_state="PRESENT",
                    remediation_operation="DELETE_RECORD",
                    remediation_state="ABSENT",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Export bundle still present.",
                )
            else:
                return ResourceCompliance(
                    system_id=system_id,
                    resource_id=resource_id,
                    resource_type=res_type,
                    required_operation=req_op,
                    condition=condition,
                    is_compliant=True,
                    evidence_id=admissible_evidence_id,
                    current_state="ABSENT",
                    verification_operation=verif_op,
                    verification_state=verif_state,
                    reason="Export bundle confirmed absent.",
                )

        # Fallback generic
        return ResourceCompliance(
            system_id=system_id,
            resource_id=resource_id,
            resource_type=res_type,
            required_operation=req_op,
            condition=condition,
            is_compliant=True,
            evidence_id=admissible_evidence_id,
            current_state="ABSENT",
            verification_operation="VERIFY_RECORD_ABSENT",
            verification_state="ABSENT",
        )

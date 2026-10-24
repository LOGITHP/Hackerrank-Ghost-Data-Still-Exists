"""Plans and orders findings, proposed remediation, and verification steps.
Strictly adheres to problem statement phase ordering, operation prioritization, and tie-breaking.
"""

from typing import Any, Dict, List
from pydantic import BaseModel
from code.engine.policy_engine import ResourceCompliance


# Operation prioritization maps
FINDING_ORDER = {
    "REPORT_REMAINING_RECORD": 1,
    "REPORT_EXPOSED_PII": 2,
    "REPORT_ACTIVE_DATA_FLOW": 3,
    "REPORT_RESTORE_RISK": 4,
}

REMEDIATION_ORDER = {
    "DISABLE_DATA_FLOW": 1,
    "BLOCK_RESTORE": 2,
    "DELETE_RECORD": 3,
    "REDACT_RECORD": 4,
    "ANONYMIZE_RECORD": 5,
}

VERIFICATION_ORDER = {
    "VERIFY_RECORD_ABSENT": 1,
    "VERIFY_RECORD_PRESENT": 2,
    "VERIFY_RECORD_REDACTED": 3,
    "VERIFY_RECORD_ANONYMIZED": 4,
    "VERIFY_DATA_FLOW_DISABLED": 5,
    "VERIFY_RESTORE_BLOCKED": 6,
}


class Step(BaseModel):
    step_no: int
    phase: str
    system_id: str
    resource_id: str
    operation: str
    state: str
    evidence_id: str


class RemediationPlanner:
    """Constructs fully ordered steps array for COMPLETE and INCOMPLETE cases."""

    @staticmethod
    def plan_steps(
        evaluations: List[ResourceCompliance],
        is_complete: bool,
    ) -> List[Dict[str, Any]]:
        """Generate ordered list of step dicts."""
        if not evaluations:
            return []

        # Deduplicate evaluations by (system_id, resource_id)
        unique_evals: Dict[str, ResourceCompliance] = {}
        for ev in evaluations:
            key = f"{ev.system_id}:{ev.resource_id}"
            if key not in unique_evals:
                unique_evals[key] = ev
            else:
                # If duplicate, prefer non-compliant finding
                if not ev.is_compliant:
                    unique_evals[key] = ev

        eval_list = list(unique_evals.values())

        if is_complete:
            # COMPLETE cases contain ONLY evidence-backed verification steps
            verif_items = []
            for ev in eval_list:
                priority = VERIFICATION_ORDER.get(ev.verification_operation, 99)
                verif_items.append((priority, ev.system_id, ev.resource_id, ev))

            # Sort by priority, then system_id asc, then resource_id asc
            verif_items.sort(key=lambda x: (x[0], x[1], x[2]))

            steps: List[Dict[str, Any]] = []
            for i, (_, _, _, ev) in enumerate(verif_items, start=1):
                steps.append({
                    "step_no": i,
                    "phase": "VERIFICATION",
                    "system_id": ev.system_id,
                    "resource_id": ev.resource_id,
                    "operation": ev.verification_operation,
                    "state": ev.verification_state,
                    "evidence_id": ev.evidence_id,
                })
            return steps

        # INCOMPLETE cases:
        # Phase 1: FINDINGS for all non-compliant resources (with evidence_id)
        # Phase 2: REMEDIATION for non-compliant resources (with empty evidence_id)
        # Phase 3: VERIFICATION for ALL resources (with empty evidence_id)

        findings_items = []
        remediation_items = []
        for ev in eval_list:
            if not ev.is_compliant:
                f_op = ev.finding_operation or "REPORT_REMAINING_RECORD"
                f_pri = FINDING_ORDER.get(f_op, 99)
                findings_items.append((f_pri, ev.system_id, ev.resource_id, ev))

                r_op = ev.remediation_operation or "DELETE_RECORD"
                r_pri = REMEDIATION_ORDER.get(r_op, 99)
                remediation_items.append((r_pri, ev.system_id, ev.resource_id, ev))

        findings_items.sort(key=lambda x: (x[0], x[1], x[2]))
        remediation_items.sort(key=lambda x: (x[0], x[1], x[2]))

        verif_items = []
        for ev in eval_list:
            v_pri = VERIFICATION_ORDER.get(ev.verification_operation, 99)
            verif_items.append((v_pri, ev.system_id, ev.resource_id, ev))

        verif_items.sort(key=lambda x: (x[0], x[1], x[2]))

        steps: List[Dict[str, Any]] = []
        step_idx = 1

        # Add Findings
        for _, _, _, ev in findings_items:
            steps.append({
                "step_no": step_idx,
                "phase": "FINDING",
                "system_id": ev.system_id,
                "resource_id": ev.resource_id,
                "operation": ev.finding_operation or "REPORT_REMAINING_RECORD",
                "state": ev.finding_state or ev.current_state,
                "evidence_id": ev.evidence_id,
            })
            step_idx += 1

        # Add Remediation
        for _, _, _, ev in remediation_items:
            steps.append({
                "step_no": step_idx,
                "phase": "REMEDIATION",
                "system_id": ev.system_id,
                "resource_id": ev.resource_id,
                "operation": ev.remediation_operation or "DELETE_RECORD",
                "state": ev.remediation_state or "ABSENT",
                "evidence_id": "",
            })
            step_idx += 1

        # Add Future Verification
        for _, _, _, ev in verif_items:
            steps.append({
                "step_no": step_idx,
                "phase": "VERIFICATION",
                "system_id": ev.system_id,
                "resource_id": ev.resource_id,
                "operation": ev.verification_operation,
                "state": ev.verification_state,
                "evidence_id": "",
            })
            step_idx += 1

        return steps

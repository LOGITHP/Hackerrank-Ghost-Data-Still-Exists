"""Status determination engine mapping evaluated states to COMPLETE, INCOMPLETE, or NOT_APPLICABLE.
"""

from typing import List
from code.engine.policy_engine import ResourceCompliance


class StatusEngine:
    """Determines the overarching case status based on request validity and resource compliance."""

    @staticmethod
    def determine_status(
        is_applicable_deletion: bool,
        evaluations: List[ResourceCompliance],
    ) -> str:
        """Return one of COMPLETE, INCOMPLETE, NOT_APPLICABLE."""
        if not is_applicable_deletion:
            return "NOT_APPLICABLE"

        if not evaluations:
            return "INCOMPLETE"

        # If any resource is non-compliant, case is INCOMPLETE
        for ev in evaluations:
            if not ev.is_compliant:
                return "INCOMPLETE"

        return "COMPLETE"

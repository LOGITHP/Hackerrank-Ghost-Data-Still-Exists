"""Identity resolution agent mapping current and historical identifiers.
"""

from typing import Dict, Optional, Set
from pydantic import BaseModel
from code.ingestion.load_datasets import DatasetIndex


class IdentityResolutionResult(BaseModel):
    user_id: Optional[str]
    all_identifiers: Set[str]
    matched_identifier: str
    is_ambiguous: bool = False
    confidence: float = 1.0


class IdentityResolver:
    """Resolves request identifiers to internal user_id using current and historical audit records."""

    def __init__(self, dataset_index: DatasetIndex):
        self.index = dataset_index

    def resolve(self, request_email: str) -> IdentityResolutionResult:
        """Resolve request email or identifier to user_id and all historical aliases."""
        if not request_email:
            return IdentityResolutionResult(
                user_id=None,
                all_identifiers=set(),
                matched_identifier="",
                is_ambiguous=True,
                confidence=0.0,
            )

        norm = request_email.strip().lower()
        user_id = self.index.id_to_user_id.get(norm)

        if not user_id:
            # Fallback search across user identities
            for uid, id_set in self.index.user_to_ids.items():
                if norm in id_set:
                    user_id = uid
                    break

        if not user_id:
            return IdentityResolutionResult(
                user_id=None,
                all_identifiers={norm},
                matched_identifier=norm,
                is_ambiguous=True,
                confidence=0.0,
            )

        all_ids = self.index.user_to_ids.get(user_id, {norm})
        return IdentityResolutionResult(
            user_id=user_id,
            all_identifiers=all_ids,
            matched_identifier=norm,
            is_ambiguous=False,
            confidence=1.0,
        )

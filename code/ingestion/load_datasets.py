"""Load, validate, and index all structured challenge datasets.
"""

import os
from typing import Any, Dict, List, Optional, Set
import pandas as pd
from pydantic import BaseModel, Field


class DatasetIndex:
    """Indexed collections for fast retrieval of identities, activities, rules, and evidence manifest."""

    def __init__(
        self,
        requests_df: pd.DataFrame,
        identities_df: pd.DataFrame,
        audit_log_df: pd.DataFrame,
        activity_df: pd.DataFrame,
        rules_df: pd.DataFrame,
        evidence_files_df: pd.DataFrame,
    ):
        self.requests_df = requests_df
        self.identities_df = identities_df
        self.audit_log_df = audit_log_df
        self.activity_df = activity_df
        self.rules_df = rules_df
        self.evidence_files_df = evidence_files_df

        # Pre-process timestamps
        if "event_time" in self.activity_df.columns:
            self.activity_df["event_dt"] = pd.to_datetime(self.activity_df["event_time"])
        if "captured_at" in self.evidence_files_df.columns:
            self.evidence_files_df["captured_dt"] = pd.to_datetime(self.evidence_files_df["captured_at"])

        # Build identity indexes
        self.id_to_user_id: Dict[str, str] = {}
        self.user_to_ids: Dict[str, Set[str]] = {}
        self._build_identity_index()

        # Build rules index
        self.rules_by_category: Dict[str, Dict[str, str]] = {}
        for _, r in self.rules_df.iterrows():
            cat = str(r.get("data_category", ""))
            self.rules_by_category[cat] = {
                "rule_id": str(r.get("rule_id", "")),
                "data_category": cat,
                "required_action": str(r.get("required_action", "")),
                "condition": str(r.get("condition", "")),
            }

        # System to category mapping
        sys_cat_map = {
            "account_service": "USER_PROFILE",
            "search_service": "SEARCH_INDEX_ENTRY",
            "support_platform": "SUPPORT_MESSAGE",
            "analytics_platform": "ANALYTICS_PROFILE",
            "export_service": "USER_EXPORT",
            "security_service": "SECURITY_AUDIT_LOG",
            "backup_service": "BACKUP_ARCHIVE",
            "identity_service": "ACCOUNT_TOMBSTONE",
            "integration_service": "PRODUCT_TELEMETRY",
        }
        self.rules_by_system: Dict[str, Dict[str, str]] = {}
        for sys_id, cat in sys_cat_map.items():
            rule = self.rules_by_category.get(cat, {})
            self.rules_by_system[sys_id] = {
                "rule_id": rule.get("rule_id", ""),
                "resource_type": cat,
                "required_operation": rule.get("required_action", "DELETE"),
                "condition": rule.get("condition", ""),
            }

        # Build evidence manifest index
        self.evidence_by_id: Dict[str, Dict[str, Any]] = {}
        for _, r in self.evidence_files_df.iterrows():
            ev_id = str(r.get("evidence_id") or r.get("file_id") or "")
            self.evidence_by_id[ev_id] = {
                "evidence_id": ev_id,
                "file_path": r.get("file_path", ""),
                "file_type": r.get("file_type", r.get("origin", "")),
                "captured_at": r.get("captured_at", ""),
                "captured_dt": r.get("captured_dt"),
                "system_id": r.get("system_id", ""),
                "description": r.get("description", ""),
            }

    def _build_identity_index(self):
        """Map every current and historical identifier to user_id."""
        for _, r in self.identities_df.iterrows():
            uid = str(r["user_id"])
            if uid not in self.user_to_ids:
                self.user_to_ids[uid] = set()
            self.user_to_ids[uid].add(uid.lower())
            self.id_to_user_id[uid.lower()] = uid

            for field in ["email", "phone", "name", "email_hash"]:
                val = r.get(field)
                if pd.notna(val) and str(val).strip():
                    norm = str(val).strip().lower()
                    self.id_to_user_id[norm] = uid
                    self.user_to_ids[uid].add(norm)

        for _, a in self.audit_log_df.iterrows():
            uid = str(a["user_id"])
            if uid not in self.user_to_ids:
                self.user_to_ids[uid] = set()
            self.user_to_ids[uid].add(uid.lower())
            self.id_to_user_id[uid.lower()] = uid

            for field in ["old_value", "new_value"]:
                val = a.get(field)
                if pd.notna(val) and str(val).strip():
                    norm = str(val).strip().lower()
                    self.id_to_user_id[norm] = uid
                    self.user_to_ids[uid].add(norm)


def load_all_datasets(data_dir: str = "dataset", use_sample: bool = False) -> DatasetIndex:
    """Load all required CSV datasets from the workspace dataset directory."""
    req_filename = "sample_deletion_requests.csv" if use_sample else "deletion_requests.csv"
    req_path = os.path.join(data_dir, req_filename)

    requests_df = pd.read_csv(req_path)
    identities_df = pd.read_csv(os.path.join(data_dir, "user_identities.csv"))
    audit_log_df = pd.read_csv(os.path.join(data_dir, "user_audit_log.csv"))
    activity_df = pd.read_csv(os.path.join(data_dir, "system_activity.csv"))
    rules_df = pd.read_csv(os.path.join(data_dir, "deletion_rules.csv"))
    evidence_files_df = pd.read_csv(os.path.join(data_dir, "evidence_files.csv"))

    return DatasetIndex(
        requests_df=requests_df,
        identities_df=identities_df,
        audit_log_df=audit_log_df,
        activity_df=activity_df,
        rules_df=rules_df,
        evidence_files_df=evidence_files_df,
    )

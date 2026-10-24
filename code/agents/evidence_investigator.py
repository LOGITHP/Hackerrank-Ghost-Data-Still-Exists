"""Evidence investigator agent correlating multi-system evidence and activity logs.
Reconstructs resource states at audit_at and pairs resources with admissible evidence IDs.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd
from code.ingestion.evidence_loader import EvidenceRecord, EvidenceStore
from code.ingestion.load_datasets import DatasetIndex
from code.engine.temporal_filter import TemporalFilter


class InvestigatedResource:
    """Represents a discovered resource, its observed state, and supporting evidence."""

    def __init__(
        self,
        system_id: str,
        resource_id: str,
        observed_state: Dict[str, Any],
        evidence_id: str,
        evidence_timestamp: Optional[pd.Timestamp] = None,
    ):
        self.system_id = system_id
        self.resource_id = resource_id
        self.observed_state = observed_state
        self.evidence_id = evidence_id
        self.evidence_timestamp = evidence_timestamp


class EvidenceInvestigator:
    """Investigates admissible evidence files and system activity logs for a specific request."""

    def __init__(self, dataset_index: DatasetIndex, evidence_store: EvidenceStore):
        self.index = dataset_index
        self.store = evidence_store

    def investigate(
        self,
        user_id: str,
        user_identifiers: Set[str],
        requested_at: Any,
        reported_at: Any,
        audit_at: Any,
        reported_status: str = "",
    ) -> List[InvestigatedResource]:
        """Perform comprehensive investigation of all resources tied to the user."""
        audit_dt = TemporalFilter.parse_timestamp(audit_at)
        req_dt = TemporalFilter.parse_timestamp(requested_at)
        rep_dt = TemporalFilter.parse_timestamp(reported_at)

        # 1. Collect all admissible evidence records for this user (req_dt - 24h <= captured_dt <= audit_dt)
        matching_evidence_recs: List[EvidenceRecord] = []
        for rec in self.store.records:
            if rec.captured_dt and audit_dt and rec.captured_dt > audit_dt:
                continue  # Inadmissible: captured after cutoff
            if rec.captured_dt and req_dt and rec.captured_dt < (req_dt - pd.Timedelta(hours=24)):
                continue  # Captured long before deletion request
            if rec.matches_user(user_identifiers):
                matching_evidence_recs.append(rec)

        # 2. Collect resources from system activity logs
        # Admissible system activity: event_dt <= audit_dt
        admissible_act = TemporalFilter.filter_activity(self.index.activity_df, audit_dt)

        # Filter activity in execution window: between requested_at and reported_at (+/- 2 hours)
        window_start = (req_dt - pd.Timedelta(hours=2)) if req_dt is not None else None
        window_end = (rep_dt + pd.Timedelta(hours=2)) if rep_dt is not None else None

        worker_events = admissible_act[admissible_act["source_system"] == "deletion_worker"]
        if window_start is not None and window_end is not None:
            worker_window = worker_events[
                (worker_events["event_dt"] >= window_start) & (worker_events["event_dt"] <= window_end)
            ]
        else:
            worker_window = worker_events

        # Identify all candidate resources
        # A map of resource_id -> dict of properties
        candidate_resources: Dict[str, Dict[str, Any]] = {}

        # First, add resources from evidence matches
        for rec in matching_evidence_recs:
            rid = rec.resource_id
            sys_id = rec.system_id
            if not sys_id or sys_id == "unknown":
                sys_id = self._infer_system_id(rid)

            if rid not in candidate_resources:
                candidate_resources[rid] = {
                    "system_id": sys_id,
                    "evidence_recs": [],
                    "evidence_id": rec.evidence_id,
                }
            candidate_resources[rid]["evidence_recs"].append(rec)
            # Prefer later evidence captures that are still admissible
            candidate_resources[rid]["evidence_id"] = rec.evidence_id

        # Also find candidate account in worker activity near reported_at if not present
        account_rid = None
        for rid in candidate_resources.keys():
            if rid.startswith("account_"):
                account_rid = rid
                break

        if not account_rid and len(worker_window) > 0:
            acc_events = worker_window[worker_window["target_system"] == "account_service"]
            if len(acc_events) > 0:
                acc_events = acc_events.copy()
                acc_events["delta"] = (acc_events["event_dt"] - rep_dt).abs()
                closest_acc = acc_events.sort_values("delta").iloc[0]
                account_rid = closest_acc["resource_id"]
                candidate_resources[account_rid] = {
                    "system_id": "account_service",
                    "evidence_recs": [],
                    "evidence_id": "",
                }

        # 3. For each candidate resource, evaluate its state and find supporting admissible evidence_id
        investigated: List[InvestigatedResource] = []

        for rid, info in candidate_resources.items():
            sys_id = info["system_id"]
            ev_recs = info["evidence_recs"]
            chosen_ev_id = info.get("evidence_id", "")

            # Look up any activity records for this resource
            res_act = admissible_act[admissible_act["resource_id"] == rid]
            del_op = res_act[res_act["source_system"] == "deletion_worker"]

            failed_worker_op = False
            if len(del_op) > 0:
                last_del = del_op.sort_values("event_dt").iloc[-1]
                if last_del["reported_result"] == "FAILED":
                    failed_worker_op = True

            # Check if any sync or recreation event occurred after deletion
            recreated = False
            sync_events = res_act[res_act["event_type"].isin(["SYNC_RECORD", "RESTORE_RECORD", "CREATE_RECORD"])]
            if len(sync_events) > 0:
                recreated = True

            # Initialize observed state
            observed_state: Dict[str, Any] = {
                "is_present": False,
                "is_redacted": True,
                "is_anonymized": True,
                "is_flow_disabled": True,
                "is_restore_blocked": True,
                "has_exposed_pii": False,
                "has_restore_risk": False,
                "has_active_flow": False,
            }

            # Evaluate state from actual evidence records if present
            has_evidence_state = False
            for erec in ev_recs:
                data = erec.data
                raw = erec.raw_text

                # Check account lookup status
                if sys_id == "account_service":
                    if "status_code" in data:
                        has_evidence_state = True
                        observed_state["is_present"] = (data["status_code"] == 200)
                    elif "rows=0" in raw or "status=404" in raw:
                        has_evidence_state = True
                        observed_state["is_present"] = False
                    elif "rows=1" in raw or "status=200" in raw:
                        has_evidence_state = True
                        observed_state["is_present"] = True

                # Check search index status
                elif sys_id == "search_service":
                    if "hits" in data:
                        has_evidence_state = True
                        tot = data.get("hits", {}).get("total", 0)
                        observed_state["is_present"] = (tot > 0)
                    elif "result=hit" in raw:
                        has_evidence_state = True
                        observed_state["is_present"] = True
                    elif "result=miss" in raw:
                        has_evidence_state = True
                        observed_state["is_present"] = False

                # Check active flow
                elif sys_id == "integration_service":
                    if "enabled" in data:
                        has_evidence_state = True
                        en = data["enabled"]
                        observed_state["has_active_flow"] = bool(en)
                        observed_state["is_flow_disabled"] = not bool(en)
                    elif "connector_enabled=true" in raw:
                        has_evidence_state = True
                        observed_state["has_active_flow"] = True
                        observed_state["is_flow_disabled"] = False
                    elif "connector_enabled=false" in raw:
                        has_evidence_state = True
                        observed_state["has_active_flow"] = False
                        observed_state["is_flow_disabled"] = True

                # Check restore allowed
                elif sys_id == "backup_service":
                    if "restore_allowed" in data:
                        has_evidence_state = True
                        ra = data["restore_allowed"]
                        observed_state["has_restore_risk"] = bool(ra)
                        observed_state["is_restore_blocked"] = not bool(ra)
                    elif "restore_allowed=true" in raw:
                        has_evidence_state = True
                        observed_state["has_restore_risk"] = True
                        observed_state["is_restore_blocked"] = False
                    elif "restore_allowed=false" in raw:
                        has_evidence_state = True
                        observed_state["has_restore_risk"] = False
                        observed_state["is_restore_blocked"] = True

                # Check analytics PII
                elif sys_id == "analytics_platform":
                    has_evidence_state = True
                    has_pii = any(data.get(k) for k in ["email", "phone", "email_hash", "customer_reference", "user_id"])
                    if "rows=1" in raw and ("correlation_key=" in raw or "email_opt_in=true" in raw):
                        has_pii = True
                    if has_pii:
                        observed_state["has_exposed_pii"] = True
                        observed_state["is_anonymized"] = False
                    else:
                        observed_state["is_anonymized"] = True

                # Check support ticket redaction
                elif sys_id == "support_platform":
                    has_evidence_state = True
                    msg = str(data.get("message_text", "") or data.get("message_excerpt", ""))
                    req_em = data.get("requester_email")
                    if req_em or erec.user_references.intersection(user_identifiers):
                        if "[REDACTED]" in msg or req_em is None:
                            observed_state["is_redacted"] = True
                        else:
                            observed_state["has_exposed_pii"] = True
                            observed_state["is_redacted"] = False
                    else:
                        observed_state["is_redacted"] = True

                # Check security audit records
                elif sys_id == "security_service":
                    has_evidence_state = True
                    observed_state["is_present"] = True

                elif sys_id == "export_service":
                    has_evidence_state = True
                    observed_state["is_present"] = True

            # If evidence did not specify state directly, fall back to worker activity and recreation logs
            if not has_evidence_state:
                if failed_worker_op or recreated:
                    if sys_id in ["account_service", "search_service", "export_service"]:
                        observed_state["is_present"] = True
                    elif sys_id == "analytics_platform":
                        observed_state["is_anonymized"] = False
                        observed_state["has_exposed_pii"] = True
                    elif sys_id == "support_platform":
                        observed_state["is_redacted"] = False
                        observed_state["has_exposed_pii"] = True
                    elif sys_id == "integration_service":
                        observed_state["is_flow_disabled"] = False
                        observed_state["has_active_flow"] = True
                    elif sys_id == "backup_service":
                        observed_state["is_restore_blocked"] = False
                        observed_state["has_restore_risk"] = True
                    elif sys_id == "identity_service":
                        observed_state["is_redacted"] = False
                        observed_state["has_exposed_pii"] = True

            # If no evidence_id found yet, select the best admissible evidence file covering this system
            if not chosen_ev_id:
                chosen_ev_id = self._select_fallback_admissible_evidence(sys_id, audit_dt)

            investigated.append(InvestigatedResource(
                system_id=sys_id,
                resource_id=rid,
                observed_state=observed_state,
                evidence_id=chosen_ev_id,
            ))

        return investigated

    def _infer_system_id(self, resource_id: str) -> str:
        if resource_id.startswith("account_"):
            return "account_service"
        if resource_id.startswith("analytics_"):
            return "analytics_platform"
        if resource_id.startswith("support_"):
            return "support_platform"
        if resource_id.startswith("search_"):
            return "search_service"
        if resource_id.startswith("data_flow_"):
            return "integration_service"
        if resource_id.startswith("backup_"):
            return "backup_service"
        if resource_id.startswith("tombstone_"):
            return "identity_service"
        if resource_id.startswith("audit_record_"):
            return "security_service"
        if resource_id.startswith("export_"):
            return "export_service"
        return "account_service"

    def _select_fallback_admissible_evidence(self, system_id: str, audit_dt: Optional[pd.Timestamp]) -> str:
        """Find an admissible evidence file that covers this system."""
        admissible = self.index.evidence_files_df.copy()
        if audit_dt and "captured_dt" in admissible.columns:
            admissible = admissible[admissible["captured_dt"] <= audit_dt]

        # Prioritize matching system_id
        sys_matches = admissible[admissible["system_id"] == system_id] if "system_id" in admissible.columns else pd.DataFrame()
        if len(sys_matches) > 0:
            first_match = sys_matches.iloc[0]
            return str(first_match.get("evidence_id") or first_match.get("file_id"))

        # Fallback to the latest admissible evidence file
        if len(admissible) > 0:
            latest = admissible.sort_values("captured_dt", ascending=False).iloc[0]
            return str(latest.get("evidence_id") or latest.get("file_id"))

        return "evidence_01"

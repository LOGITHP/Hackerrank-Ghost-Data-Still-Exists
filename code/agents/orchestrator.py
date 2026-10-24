"""LangGraph stateful workflow orchestrating the 9-stage deletion audit pipeline.
"""

import json
from typing import Any, Dict, List, Optional, Set, TypedDict
from langgraph.graph import END, StateGraph
from code.agents.evidence_investigator import EvidenceInvestigator, InvestigatedResource
from code.agents.identity_resolver import IdentityResolver
from code.agents.request_analyzer import RequestAnalyzer
from code.engine.policy_engine import PolicyEngine, ResourceCompliance
from code.engine.remediation_planner import RemediationPlanner
from code.engine.status_engine import StatusEngine
from code.ingestion.evidence_loader import EvidenceStore
from code.ingestion.load_datasets import DatasetIndex


class AuditState(TypedDict):
    case_id: str
    email: str
    requested_at: str
    reported_at: str
    reported_status: str
    audit_at: str
    request_text: str
    user_id: Optional[str]
    user_identifiers: List[str]
    is_applicable: bool
    investigated_resources: List[Dict[str, Any]]
    evaluations: List[Dict[str, Any]]
    deletion_status: str
    steps: List[Dict[str, Any]]
    steps_json: str
    errors: List[str]


class AuditOrchestrator:
    """Compiles and runs the LangGraph audit pipeline."""

    def __init__(
        self,
        dataset_index: DatasetIndex,
        evidence_store: EvidenceStore,
        request_analyzer: RequestAnalyzer,
    ):
        self.index = dataset_index
        self.store = evidence_store
        self.request_analyzer = request_analyzer
        self.identity_resolver = IdentityResolver(dataset_index)
        self.evidence_investigator = EvidenceInvestigator(dataset_index, evidence_store)
        self.policy_engine = PolicyEngine(dataset_index.rules_by_system)
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AuditState)

        # Register nodes
        builder.add_node("request_understanding", self._node_request_understanding)
        builder.add_node("identity_resolution", self._node_identity_resolution)
        builder.add_node("evidence_investigation", self._node_evidence_investigation)
        builder.add_node("policy_evaluation", self._node_policy_evaluation)
        builder.add_node("remediation_planning", self._node_remediation_planning)
        builder.add_node("status_determination", self._node_status_determination)
        builder.add_node("output_generation", self._node_output_generation)

        # Set entry point
        builder.set_entry_point("request_understanding")

        # Conditional route: if not applicable, bypass directly to output generation
        builder.add_conditional_edges(
            "request_understanding",
            self._route_applicability,
            {
                "not_applicable": "output_generation",
                "applicable": "identity_resolution",
            },
        )

        builder.add_edge("identity_resolution", "evidence_investigation")
        builder.add_edge("evidence_investigation", "policy_evaluation")
        builder.add_edge("policy_evaluation", "status_determination")
        builder.add_edge("status_determination", "remediation_planning")
        builder.add_edge("remediation_planning", "output_generation")
        builder.add_edge("output_generation", END)

        return builder.compile()

    def _route_applicability(self, state: AuditState) -> str:
        return "applicable" if state.get("is_applicable", True) else "not_applicable"

    def _node_request_understanding(self, state: AuditState) -> Dict[str, Any]:
        analysis = self.request_analyzer.analyze(state.get("request_text", ""))
        is_app = analysis.is_deletion
        if not is_app:
            return {
                "is_applicable": False,
                "deletion_status": "NOT_APPLICABLE",
                "steps": [],
                "steps_json": "[]",
            }
        return {"is_applicable": True}

    def _node_identity_resolution(self, state: AuditState) -> Dict[str, Any]:
        res = self.identity_resolver.resolve(state.get("email", ""))
        return {
            "user_id": res.user_id,
            "user_identifiers": list(res.all_identifiers),
        }

    def _node_evidence_investigation(self, state: AuditState) -> Dict[str, Any]:
        user_id = state.get("user_id") or ""
        identifiers = set(state.get("user_identifiers", []))
        investigated = self.evidence_investigator.investigate(
            user_id=user_id,
            user_identifiers=identifiers,
            requested_at=state.get("requested_at"),
            reported_at=state.get("reported_at"),
            audit_at=state.get("audit_at"),
            reported_status=state.get("reported_status", ""),
        )
        # Serialize investigated resources
        serialized = []
        for inv in investigated:
            serialized.append({
                "system_id": inv.system_id,
                "resource_id": inv.resource_id,
                "observed_state": inv.observed_state,
                "evidence_id": inv.evidence_id,
            })
        return {"investigated_resources": serialized}

    def _node_policy_evaluation(self, state: AuditState) -> Dict[str, Any]:
        investigated = state.get("investigated_resources", [])
        evaluations: List[Dict[str, Any]] = []

        for inv in investigated:
            comp = self.policy_engine.evaluate_resource(
                system_id=inv["system_id"],
                resource_id=inv["resource_id"],
                observed_state=inv["observed_state"],
                admissible_evidence_id=inv["evidence_id"],
            )
            evaluations.append(comp.model_dump())

        return {"evaluations": evaluations}

    def _node_status_determination(self, state: AuditState) -> Dict[str, Any]:
        evals_data = state.get("evaluations", [])
        eval_objs = [ResourceCompliance(**e) for e in evals_data]
        status = StatusEngine.determine_status(
            is_applicable_deletion=state.get("is_applicable", True),
            evaluations=eval_objs,
        )
        return {"deletion_status": status}

    def _node_remediation_planning(self, state: AuditState) -> Dict[str, Any]:
        status = state.get("deletion_status", "INCOMPLETE")
        evals_data = state.get("evaluations", [])
        eval_objs = [ResourceCompliance(**e) for e in evals_data]

        is_comp = (status == "COMPLETE")
        planned_steps = RemediationPlanner.plan_steps(eval_objs, is_complete=is_comp)
        return {"steps": planned_steps}

    def _node_output_generation(self, state: AuditState) -> Dict[str, Any]:
        status = state.get("deletion_status", "INCOMPLETE")
        if status == "NOT_APPLICABLE":
            return {"steps_json": "[]", "steps": []}

        steps = state.get("steps", [])
        serialized_json = json.dumps(steps, separators=(",", ":"))
        return {"steps_json": serialized_json}

    def process_case(self, case_row: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the LangGraph workflow on a single case row."""
        initial_state: AuditState = {
            "case_id": str(case_row.get("case_id", "")),
            "email": str(case_row.get("email", "")),
            "requested_at": str(case_row.get("requested_at", "")),
            "reported_at": str(case_row.get("reported_at", "")),
            "reported_status": str(case_row.get("reported_status", "")),
            "audit_at": str(case_row.get("audit_at", "")),
            "request_text": str(case_row.get("request_text", "")),
            "user_id": None,
            "user_identifiers": [],
            "is_applicable": True,
            "investigated_resources": [],
            "evaluations": [],
            "deletion_status": "INCOMPLETE",
            "steps": [],
            "steps_json": "[]",
            "errors": [],
        }

        final_state = self.graph.invoke(initial_state)
        return {
            "case_id": final_state["case_id"],
            "deletion_status": final_state["deletion_status"],
            "steps_json": final_state["steps_json"],
        }

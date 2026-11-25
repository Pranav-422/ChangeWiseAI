"""Request and response models. FastAPI's OpenAPI document is generated from these."""
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["ADMIN", "ENGINEERING", "PURCHASING", "PRODUCTION_PLANNER", "QUALITY", "VIEWER"]
Json = dict[str, Any]


class In(BaseModel):
    """Requests: unknown fields are refused, so a client cannot send a role, a user ID or a result."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Out(BaseModel):
    model_config = ConfigDict(extra="ignore")


# Errors, health, access -------------------------------------------------------------------------

class ErrorBody(Out):
    code: str
    message: str
    details: list[Any]
    request_id: Optional[str]


class ErrorResponse(Out):
    error: ErrorBody


class Health(Out):
    status: str


class Ready(Out):
    status: str
    database: bool
    ai: str
    storage: bool
    auth: bool


class Me(Out):
    user_id: str
    email: str
    name: str
    role: Role
    permissions: list[str]


class Permissions(Out):
    role: Role
    granted: list[str]
    matrix: dict[str, list[str]]


class ProfileUpdate(In):
    full_name: str = Field(min_length=1, max_length=120)


class UserRow(Out):
    user_id: str
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: str
    updated_at: str


class UserUpdate(In):
    role: Optional[Role] = None
    is_active: Optional[bool] = None


# Changes ----------------------------------------------------------------------------------------

class Scenario(Out):
    scenario_id: str
    description: str


class LatestReview(Out):
    review_id: str
    status: str
    validation_status: str
    created_at: str


class LatestRun(Out):
    run_id: str
    decision: str
    created_at: str
    approval: Optional[str]
    closed_at: Optional[str]


class Change(Out):
    change_id: str
    part_number: str
    new_material_id: str
    old_revision: str
    new_revision: str
    effective_week: int
    use_up_end_week: int
    interchangeability: bool
    reason: Optional[str]
    approver: Optional[str]
    approval_status: str
    approval_week: Optional[int]
    created_at: str


class ChangeRow(Change):
    scenarios: list[Scenario]
    validation_status: str
    stage: int
    latest_review: Optional[LatestReview]
    latest_run: Optional[LatestRun]


class BomNode(Out):
    material_id: str
    name: str
    type: str
    revision: str
    status: str
    description: Optional[str]


class BomEdge(Out):
    parent: str
    child: str
    quantity: float
    effective_from: Optional[int]
    effective_to: Optional[int]


class BomPath(Out):
    material_id: str
    assembly: str
    assembly_type: Optional[str]
    path_ids: list[str]
    quantity: float


class BomImpact(Out):
    change_id: str
    old_material_id: str
    new_material_id: str
    impact_status: str
    direct_parents: list[str]
    indirect_parents: list[str]
    finished_products: list[str]
    cycles: list[list[str]]
    nodes: list[BomNode]
    edges: list[BomEdge]
    paths: list[BomPath]


class Week(Out):
    week: int
    demand: float
    shortage: float
    applicable_revision: Optional[str] = None
    rev_b_opening: float
    rev_b_receipts: float
    rev_b_reserved: float
    rev_b_available: float
    rev_b_safety_stock: float
    rev_b_usable: float
    rev_b_usage: float
    rev_b_closing: float
    rev_c_opening: float
    rev_c_receipts: float
    rev_c_reserved: float
    rev_c_available: float
    rev_c_safety_stock: float
    rev_c_usable: float
    rev_c_usage: float
    rev_c_closing: float


class Issue(Out):
    code: str
    status: str
    record: str
    description: str
    resolution: str


class Excess(Out):
    rev_b_leftover_at_use_up_units: float
    rev_b_post_use_up_receipts: float
    rev_b_scrap_units: float
    rev_b_scrap_from_safety_stock: float
    rev_b_reserved_excluded: float
    rev_b_unit_cost: float
    rev_b_scrap_value: float
    rev_c_closing_units: float
    average_weekly_demand: float
    coverage_weeks: float
    rev_c_unit_cost: float
    rev_c_excess_value: float
    total_excess_value: float


class MaterialRow(Out):
    material_id: str
    revision: str
    name: str
    unit_cost: float


class StockRow(Out):
    material_id: str
    on_hand: int
    reserved: int
    safety_stock: int
    inventory_date: str


class OrderRow(Out):
    po_id: str
    material_id: str
    supplier_id: str
    supplier_name: Optional[str]
    supplier_status: Optional[str]
    quantity: Optional[int]
    order_week: Optional[int]
    arrival_week: Optional[int]
    status: str
    change_deadline_week: Optional[int]


class MaterialBalance(Out):
    opening: float
    receipts: float
    used: float
    reserved: float
    scrap: float


class Inventory(Out):
    change_id: str
    scenario_id: str
    simulation_id: str
    input_hash: str
    engine_version: str
    status: str
    effective_week: Optional[int]
    use_up_end_week: Optional[int]
    horizon_weeks: int
    stored_at: Optional[str]
    weeks: list[Week]
    total_shortage_units: Optional[float]
    excess_value: Optional[float]
    excess: Optional[Excess]
    issues: list[Issue]
    materials: list[MaterialRow]
    stock: list[StockRow]
    purchase_orders: list[OrderRow]
    material_balance: Optional[MaterialBalance]


class ExceptionItem(Out):
    exception_id: str
    simulation_id: str
    change_id: str
    exception_type: str
    material_id: Optional[str]
    week: Optional[int]
    quantity: Optional[float]
    financial_impact: float
    severity_score: float
    severity_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    severity_rank: int
    description: str
    recommended_action: str
    owner_role: str
    owner_roles: list[str]
    status: Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"]
    allowed_statuses: list[str]
    updated_at: Optional[str]


class ExceptionList(Out):
    change_id: str
    scenario_id: str
    simulation_id: str
    items: list[ExceptionItem]


class ExceptionUpdate(In):
    change_id: str
    scenario: str = "base"
    status: Literal["ACKNOWLEDGED", "RESOLVED"]


class Validation(Out):
    status: str
    issues: list[Issue]


# ECN --------------------------------------------------------------------------------------------

class Document(Out):
    document_id: str
    change_id: str
    source_kind: str
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    extraction_status: str
    extraction_error: Optional[str]
    review_id: Optional[str]
    uploaded_by: Optional[str]
    uploaded_at: str
    stored: bool


class SignedUrl(Out):
    url: str
    expires_in: int


class SampleUpload(In):
    change_id: str
    scenario: str = "base"
    sample_id: str


class ManualReview(In):
    change_id: str
    scenario: str = "base"


class EcnFields(In):
    """Types and limits of each field are checked again by Member 3's schema, with a readable reason."""
    change_id: Optional[str] = Field(None, max_length=60)
    part_number: Optional[str] = Field(None, max_length=60)
    old_revision: Optional[str] = Field(None, max_length=10)
    new_revision: Optional[str] = Field(None, max_length=10)
    effective_week: Optional[int] = None
    use_up_end_week: Optional[int] = None
    interchangeability: Optional[bool] = None
    reason: Optional[str] = Field(None, max_length=500)
    approver: Optional[str] = Field(None, max_length=200)
    approval_status: Optional[Literal["APPROVED", "PENDING", "DRAFT", "REJECTED"]] = None


class EcnFieldValues(Out):
    change_id: Optional[str]
    part_number: Optional[str]
    old_revision: Optional[str]
    new_revision: Optional[str]
    effective_week: Optional[int]
    use_up_end_week: Optional[int]
    interchangeability: Optional[bool]
    reason: Optional[str]
    approver: Optional[str]
    approval_status: Optional[str]


class AmbiguousField(Out):
    field: str
    source_text: str


class ConflictValue(Out):
    value: Any
    source_text: str


class ConflictField(Out):
    field: str
    values: list[ConflictValue]


class UnsupportedValue(Out):
    field: str
    value: Any
    why: str


class FieldError(Out):
    code: str
    field: str
    message: str


class EcnExtraction(EcnFieldValues):
    source_document: Optional[str]
    extraction_source: str
    provider_error: Optional[str]
    extraction_confidence: float
    evidence: dict[str, str]
    missing_fields: list[str]
    ambiguous_fields: list[AmbiguousField]
    conflicts: list[ConflictField]
    unsupported_values: list[UnsupportedValue]


class EcnValidation(Out):
    validation_status: Literal["VALID", "INVALID", "INSUFFICIENT_DATA", "NEEDS_REVIEW"]
    missing_fields: list[str]
    ambiguous_fields: list[AmbiguousField]
    conflicts: list[ConflictField]
    validation_errors: list[FieldError]
    ready_for_planning: bool


class Review(Out):
    review_id: str
    change_id: str
    scenario_id: str
    status: Literal["NEEDS_REVIEW", "CONFIRMED"]
    document_text: str
    document_hash: str
    document: Optional[Document]
    extraction: EcnExtraction
    fields: EcnFieldValues
    validation: EcnValidation
    extraction_schema_version: str
    created_by: str
    created_at: str
    confirmed_by: Optional[str]
    confirmed_at: Optional[str]
    latest_run_id: Optional[str]


class ReviewRow(Out):
    review_id: str
    change_id: str
    scenario_id: str
    status: str
    fields: EcnFieldValues
    validation_status: str
    extraction_source: str
    created_by: str
    created_at: str
    confirmed_by: Optional[str]
    confirmed_at: Optional[str]
    document_id: Optional[str]
    original_filename: Optional[str]


class ReviewList(Out):
    items: list[ReviewRow]
    unread_documents: list[Document]
    total: int


# Planning ---------------------------------------------------------------------------------------

class OptimizeRequest(In):
    review_id: str


class StressRun(Out):
    scenario_id: str
    lead_time_shock: float
    demand_shock: float
    shortage_units: float
    excess_value: float
    zero_shortage: bool


class Robustness(Out):
    numerator: int
    denominator: int
    display: str
    scenarios: list[StressRun]


class CostBreakdown(Out):
    expedite: float
    cancellation: float
    reduction: float
    total: float


class NearTie(Out):
    plan_a: str
    plan_b: str
    secondary_cost_a: float
    secondary_cost_b: float
    absolute: float
    percent: Optional[float]


class PlanAction(BaseModel):
    """One engine action. Which keys exist depends on the action."""
    model_config = ConfigDict(extra="forbid")
    action: str = Field(max_length=40)
    po_id: Optional[str] = Field(None, max_length=40)
    supplier_id: Optional[str] = Field(None, max_length=40)
    quantity: Optional[int] = Field(None, ge=0, le=1_000_000)
    weeks: Optional[int] = Field(None, ge=0, le=104)
    from_week: Optional[int] = Field(None, ge=0, le=104)
    to_week: Optional[int] = Field(None, ge=0, le=104)
    through_week: Optional[int] = Field(None, ge=0, le=104)


class Recommendation(Out):
    plan_id: str
    rank: int
    overall_rank: int
    effective_week: int
    actions: list[Json]
    summary: str
    shortage_units: float
    excess_value: float
    action_cost: float
    action_cost_breakdown: CostBreakdown
    secondary_cost: float
    feasibility: str
    near_ties: list[NearTie]
    simulation_reference: Optional[str]
    robustness: Optional[Robustness]
    weekly: list[Week]


class Escalation(Out):
    code: str
    message: str
    plan_ids: list[str]
    evidence: list[Any]
    status: str


class Counts(Out):
    combinations: int
    candidates: int
    feasible: int
    rejected: int


class WeekOption(Out):
    effective_week: int
    plan_id: Optional[str]
    summary: Optional[str]
    shortage_units: Optional[float]
    excess_value: Optional[float]
    action_cost: Optional[float]
    secondary_cost: Optional[float]


class HardRule(Out):
    rule: str
    title: str
    violations: int


class RunApproval(Out):
    approval_id: str
    decision: Literal["APPROVED", "REJECTED"]
    modified: bool
    comment: str
    user_name: str
    role: str
    created_at: str
    closed_at: Optional[str]
    plan_id: Optional[str]
    plan_summary: Optional[str]


class Run(Out):
    run_id: str
    review_id: str
    change_id: str
    scenario_id: str
    input_hash: str
    config_hash: str
    engine_version: str
    simulator: str
    method: Optional[str]
    decision: str
    requires_planner_review: bool
    recommended_plan_id: Optional[str]
    counts: Counts
    recommendations: list[Recommendation]
    near_ties: list[NearTie]
    escalations: list[Escalation]
    effective_week_comparison: list[WeekOption]
    hard_rules: list[HardRule]
    computation_seconds: float
    created_by: str
    created_at: str
    stale: bool
    newest: bool
    approval: Optional[RunApproval]


class RunRow(Out):
    run_id: str
    change_id: str
    scenario_id: str
    decision: str
    created_by: str
    created_at: str
    approval: Optional[str]


class RunList(Out):
    items: list[RunRow]
    total: int


class RankedPlan(Out):
    plan_id: str
    rank: int
    summary: str
    effective_week: int
    shortage_units: float
    excess_value: float
    action_cost: float
    secondary_cost: float
    redundant_of: Optional[str] = None


class RankedPlans(Out):
    items: list[RankedPlan]
    total: int


class Reason(Out):
    rule: str
    code: str
    description: str


class RejectedPlan(Out):
    plan_id: str
    summary: str
    source: str
    actions: list[Json]
    rejection_reasons: list[Reason]


class RejectedPlans(Out):
    items: list[RejectedPlan]
    total: int


class PlanRobustness(Robustness):
    plan_id: str
    rank: int
    summary: str


class Configuration(Out):
    configuration: str
    assumptions: list[str]
    shortage_units: float
    shortage_weeks: list[int]
    rev_b_leftover: float
    rev_c_closing: float
    excess_value: float
    action_cost: float
    secondary_cost: float
    hard_rule_violations: int
    robustness: Robustness


class MenuOption(Out):
    label: str
    actions: list[Json]


class Menu(Out):
    name: str
    options: list[MenuOption]


# What-if ----------------------------------------------------------------------------------------

class WhatIfParse(In):
    run_id: str
    question: str = Field(min_length=1, max_length=500)


class POQuantityChange(In):
    po_id: Optional[str] = None
    revision: Optional[Literal["B", "C"]] = None
    quantity_delta: int


class WhatIfParameters(In):
    scenario_id: str = "WHATIF"
    lead_time_delta: int = 0
    demand_change_percent: float = 0
    effective_week: Optional[int] = None
    po_quantity_change: Optional[POQuantityChange] = None
    supplier_block: Optional[str] = None
    requires_confirmation: Literal[True] = True


class WhatIfParsed(Out):
    run_id: str
    question: str
    status: Literal["OK", "UNSUPPORTED_SCENARIO_REQUEST", "NEEDS_CLARIFICATION", "INVALID_PARAMETER"]
    message: str
    parameters: Optional[WhatIfParameters]
    source: str
    provider_error: Optional[str]


class WhatIfConfirm(In):
    run_id: str
    question: str = Field("", max_length=500)
    parameters: WhatIfParameters


class ComparisonRow(Out):
    measure: str
    base: Any
    alternative: Any
    change: Optional[float]


class RunException(Out):
    exception_id: str
    type: str
    week: Optional[int]
    units: float
    impact_rs: float
    severity: float
    band: str
    description: str


class ScenarioPlan(Out):
    plan_id: str
    summary: str
    shortage_units: float
    excess_value: float
    action_cost: float
    secondary_cost: float
    robustness: Optional[Robustness]
    weekly: list[Week]


class Section(Out):
    title: str
    text: str


class Explanation(Out):
    explanation_id: str
    subject_type: Literal["RUN", "WHAT_IF"]
    subject_id: str
    label: Literal["AI_GENERATED_VERIFIED", "TEMPLATE_GENERATED", "AWAITING_REVIEW"]
    source: str
    sections: list[Section]
    draft: Optional[list[Section]]
    warning: Optional[str]
    facts: Json
    verification_status: str
    verification: Optional[Json]
    created_at: str


class WhatIfResult(Out):
    scenario_id: str
    run_id: str
    question: str
    parameters: WhatIfParameters
    constrained: bool
    decision: str
    comparison: list[ComparisonRow]
    description: str
    escalations: list[Escalation]
    base_plan: Optional[ScenarioPlan]
    alternative_plan: Optional[ScenarioPlan]
    counts: Counts
    new_exceptions: list[RunException]
    explanation: Optional[Explanation]
    created_by: str
    created_at: str


class WhatIfRow(Out):
    scenario_id: str
    question: str
    created_by: str
    created_at: str


class ExplanationRequest(In):
    run_id: str


# Approval, actions ------------------------------------------------------------------------------

class PendingApproval(Out):
    run_id: str
    change_id: str
    scenario_id: str
    decision: str
    created_at: str
    plan_id: str
    plan_summary: str
    shortage_units: float
    secondary_cost: float
    robustness: str
    escalations: list[str]


class Approval(RunApproval):
    run_id: str
    change_id: str
    scenario_id: str


class ApprovalList(Out):
    pending: list[PendingApproval]
    decided: list[Approval]


class Modification(In):
    actions: list[PlanAction] = Field(max_length=30)


class DecisionRequest(In):
    decision: Literal["APPROVED", "REJECTED"]
    comment: str = Field("", max_length=2000)
    plan_id: Optional[str] = None
    modified_actions: Optional[list[PlanAction]] = Field(None, max_length=30)


class EvaluatedPlan(Out):
    plan_id: str
    summary: str
    feasibility: Literal["FEASIBLE", "REJECTED"]
    rejection_reasons: list[Reason]
    actions: list[Json]
    shortage_units: Optional[float] = None
    excess_value: Optional[float] = None
    action_cost: Optional[float] = None
    secondary_cost: Optional[float] = None
    robustness: Optional[Robustness] = None
    weekly: Optional[list[Week]] = None


class ActionItem(Out):
    action_id: str
    approval_id: str
    run_id: str
    scenario_id: str
    plan_id: Optional[str]
    plan_action_id: Optional[str]
    summary: str
    action: Json
    owner_role: str
    assignee: Optional[str]
    due_week: Optional[int]
    status: Literal["OPEN", "IN_PROGRESS", "DONE"]
    next_status: Optional[str]
    closed_at: Optional[str]
    created_at: str
    updated_at: str


class ActionUpdate(In):
    status: Optional[Literal["IN_PROGRESS", "DONE"]] = None
    assignee: Optional[str] = Field(None, max_length=120)


class StatusChange(Out):
    from_status: Optional[str]
    to_status: str
    changed_by: Optional[str]
    changed_at: str


# Audit ------------------------------------------------------------------------------------------

class AuditEvent(Out):
    seq: int
    created_at: str
    event_type: str
    entity_id: str
    user_name: str
    role: str
    payload: Json
    previous_hash: str
    event_hash: str
    source: str


class AuditPage(Out):
    items: list[AuditEvent]
    total: int
    event_types: list[str]


class Chain(Out):
    intact: bool
    broken_at: Optional[int]
    events: int
    head_hash: Optional[str]


class ReplayRequest(In):
    run_id: str


class Difference(Out):
    field: str
    original: str
    reproduced: str


class Replay(Out):
    replay_id: str
    run_id: str
    status: Literal["MATCHED", "DIFFERENT", "SNAPSHOT_ALTERED"]
    snapshot_intact: bool
    original: Json
    reproduced: Optional[Json]
    differences: list[Difference]
    created_by: str
    created_at: str


class Overview(Out):
    change: Change
    scenario_id: str
    scenarios: list[Scenario]
    validation: Validation
    stage: int
    latest_review: Optional[LatestReview]
    run: Optional[Run]
    inventory: Inventory
    exceptions: list[ExceptionItem]
    finished_products: list[str]
    pending_approvals: int
    actions: list[ActionItem]
    recent_events: list[AuditEvent]

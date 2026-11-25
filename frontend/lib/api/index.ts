import type { components } from "@/types/api";
import { http } from "./client";

type S = components["schemas"];
export type Me = S["Me"];
export type Role = Me["role"];
export type ChangeRow = S["ChangeRow"];
export type Change = S["Change"];
export type Overview = S["Overview"];
export type Inventory = S["Inventory"];
export type Week = S["Week"];
export type BomImpact = S["BomImpact"];
export type BomNode = S["BomNode"];
export type ExceptionItem = S["ExceptionItem"];
export type ExceptionList = S["ExceptionList"];
export type Review = S["Review"];
export type ReviewList = S["ReviewList"];
export type EcnFieldValues = S["EcnFieldValues"];
export type Document = S["Document"];
export type Run = S["Run"];
export type RunList = S["RunList"];
export type Recommendation = S["Recommendation"];
export type Robustness = S["Robustness"];
export type Configuration = S["Configuration"];
export type RankedPlans = S["RankedPlans"];
export type RejectedPlans = S["RejectedPlans"];
export type Menu = S["Menu"];
export type Explanation = S["Explanation"];
export type WhatIfParsed = S["WhatIfParsed"];
export type WhatIfParameters = S["WhatIfParameters"];
export type WhatIfResult = S["WhatIfResult"];
export type WhatIfRow = S["WhatIfRow"];
export type ApprovalList = S["ApprovalList"];
export type Approval = S["Approval"];
export type EvaluatedPlan = S["EvaluatedPlan"];
export type ActionItem = S["ActionItem"];
export type StatusChange = S["StatusChange"];
export type AuditEvent = S["AuditEvent"];
export type AuditPage = S["AuditPage"];
export type Chain = S["Chain"];
export type Replay = S["Replay"];
export type UserRow = S["UserRow"];

const id = encodeURIComponent;

/** Every backend call the interface makes. Business results come from here and nowhere else. */
export const api = {
  me: () => http.get<Me>("/auth/me"),
  rename: (full_name: string) => http.patch<void>("/auth/me", { full_name }),
  users: () => http.get<UserRow[]>("/admin/users"),
  updateUser: (user: string, body: S["UserUpdate"]) => http.patch<UserRow>(`/admin/users/${id(user)}`, body),

  changes: () => http.get<ChangeRow[]>("/changes"),
  overview: (change: string, scenario: string) => http.get<Overview>(`/changes/${id(change)}/overview`, { scenario }),
  bom: (change: string, scenario: string) => http.get<BomImpact>(`/changes/${id(change)}/bom-impact`, { scenario }),
  inventory: (change: string, scenario: string) => http.get<Inventory>(`/changes/${id(change)}/inventory`, { scenario }),
  simulate: (change: string, scenario: string) =>
    http.post<Inventory>(`/changes/${id(change)}/simulate`, undefined, { scenario }),
  exceptions: (change: string, scenario: string) =>
    http.get<ExceptionList>(`/changes/${id(change)}/exceptions`, { scenario }),
  updateException: (item: string, body: S["ExceptionUpdate"]) =>
    http.patch<ExceptionItem>(`/exceptions/${id(item)}`, body),

  reviews: (limit = 25, offset = 0) => http.get<ReviewList>("/ecn", { limit, offset }),
  review: (review: string) => http.get<Review>(`/ecn/${id(review)}`),
  samples: () => http.get<string[]>("/ecn/samples"),
  uploadSample: (change_id: string, scenario: string, sample_id: string) =>
    http.post<Document>("/ecn/samples", { change_id, scenario, sample_id }),
  upload: (change_id: string, scenario: string, content: File | string) => {
    const form = new FormData();
    form.set("change_id", change_id);
    form.set("scenario", scenario);
    if (typeof content === "string") form.set("text", content);
    else form.set("file", content);
    return http.post<Document>("/ecn/upload", form);
  },
  extract: (document: string) => http.post<Review>(`/ecn/${id(document)}/extract`),
  manualReview: (change_id: string, scenario: string) => http.post<Review>("/ecn/manual", { change_id, scenario }),
  documentUrl: (document: string) => http.get<S["SignedUrl"]>(`/ecn/documents/${id(document)}/url`),
  updateReview: (review: string, fields: Partial<EcnFieldValues>) => http.patch<Review>(`/ecn/${id(review)}`, fields),
  validateReview: (review: string) => http.post<Review>(`/ecn/${id(review)}/validate`),
  confirmReview: (review: string) => http.post<Review>(`/ecn/${id(review)}/confirm`),

  optimize: (review_id: string) => http.post<Run>("/planning/optimize", { review_id }),
  runs: (limit = 25, offset = 0) => http.get<RunList>("/planning/runs", { limit, offset }),
  run: (run: string) => http.get<Run>(`/planning/runs/${id(run)}`),
  plans: (run: string, limit: number, offset: number) =>
    http.get<RankedPlans>(`/planning/runs/${id(run)}/plans`, { limit, offset }),
  rejected: (run: string) => http.get<RejectedPlans>(`/planning/runs/${id(run)}/rejected-plans`),
  comparison: (run: string) => http.get<Configuration[]>(`/planning/runs/${id(run)}/comparison`),
  menus: (run: string) => http.get<Menu[]>(`/planning/runs/${id(run)}/menus`),
  explanation: (run: string) => http.get<Explanation | null>(`/planning/runs/${id(run)}/explanation`),
  explain: (run_id: string) => http.post<Explanation>("/explanations/generate", { run_id }),

  parseWhatIf: (run_id: string, question: string) =>
    http.post<WhatIfParsed>("/planning/what-if/parse", { run_id, question }),
  confirmWhatIf: (run_id: string, question: string, parameters: WhatIfParameters) =>
    http.post<WhatIfResult>("/planning/what-if/confirm", { run_id, question, parameters }),
  whatIf: (scenario: string) => http.get<WhatIfResult>(`/planning/what-if/${id(scenario)}`),
  whatIfs: (run: string) => http.get<WhatIfRow[]>(`/planning/runs/${id(run)}/what-if`),

  approvals: () => http.get<ApprovalList>("/approvals"),
  evaluate: (run: string, actions: S["PlanAction"][]) =>
    http.post<EvaluatedPlan>(`/approvals/${id(run)}/modification`, { actions }),
  decide: (run: string, body: S["DecisionRequest"]) => http.post<Approval>(`/approvals/${id(run)}/decision`, body),
  close: (approval: string) => http.post<Approval>(`/approvals/${id(approval)}/close`),

  actions: (run_id?: string) => http.get<ActionItem[]>("/actions", { run_id }),
  updateAction: (action: string, body: S["ActionUpdate"]) => http.patch<ActionItem>(`/actions/${id(action)}`, body),
  actionHistory: (action: string) => http.get<StatusChange[]>(`/actions/${id(action)}/history`),

  audit: (query: { limit: number; offset: number; event_type?: string; search?: string; entity_id?: string }) =>
    http.get<AuditPage>("/audit", query),
  chain: () => http.get<Chain>("/audit/chain"),
  replays: () => http.get<Replay[]>("/audit/replay"),
  replay: (run_id: string) => http.post<Replay>("/audit/replay", { run_id }),
};

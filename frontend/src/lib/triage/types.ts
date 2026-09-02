export type DocumentId = string;

export type DocumentRule = {
  label: string;
  detail: string;
  source: string;
};

/** A requirement satisfied by any one of several documents (e.g. title OR lease). */
export type DocumentGroupRule = {
  label: string;
  detail: string;
  anyOf: DocumentId[];
  source: string;
};

export type Allocation = {
  unit: string;
  /** Statutory split: 2 planting + 2 top-dressing per acre. */
  plantingBagsPerAcre: number;
  topDressingBagsPerAcre: number;
  /** The two above, summed. Held explicitly so the rules file stays the source. */
  bagsPerAcre: number;
  /** Absolute statutory ceiling per farmer, not a per-depot limit. */
  maxBags: number;
  pricePerBagKes: number;
};

export type Depot = {
  id: string;
  name: string;
  county: string;
  program: string;
  /** Document ids and/or documentGroup ids. */
  requires: string[];
  allocation: Allocation;
  source: string;
};

export type PaymentAtDepot = {
  cashAccepted: boolean;
  headline: string;
  notice: string;
  source: string;
};

export type SchemeRules = {
  version: string;
  note?: string;
  circular?: string;
  operatingProcedure?: string;
  paymentAtDepot?: PaymentAtDepot;
  documents: Record<DocumentId, DocumentRule>;
  documentGroups: Record<string, DocumentGroupRule>;
  depots: Depot[];
};

export type TriageInput = {
  acres: number;
  depotId: string;
  heldDocuments: DocumentId[];
};

export type Verdict = "PROCEED" | "DO_NOT_TRAVEL";

export type MissingRequirement = {
  /** Document id, or group id when a whole group is unsatisfied. */
  id: string;
  label: string;
  detail: string;
  source: string;
  /** For groups: the documents that would satisfy it. */
  satisfiedByAnyOf?: { id: DocumentId; label: string }[];
};

export type Costing = {
  bags: number;
  plantingBags: number;
  topDressingBags: number;
  unit: string;
  pricePerBagKes: number;
  totalKes: number;
  /** Whether the statutory ceiling bound the allocation rather than acreage. */
  cappedByStatutoryCeiling: boolean;
  maxBags: number;
  bagsPerAcre: number;
};

export type TriageResult = {
  verdict: Verdict;
  depot: { id: string; name: string; county: string; program: string };
  acres: number;
  missing: MissingRequirement[];
  costing: Costing;
  /** Every citation the verdict and costing rest on, deduplicated. */
  citations: string[];
  rulesVersion: string;
};

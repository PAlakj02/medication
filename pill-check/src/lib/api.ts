// Real backend client — replaces the hardcoded MEDS/RULES mock that used to
// live in this file's place (src/lib/med-data.ts, now deleted). Types match
// docs/api-contract.md exactly.

import { getCurrentIdToken } from "@/lib/firebase";

const API_BASE_URL = import.meta.env["VITE_API_BASE_URL"] ?? "http://localhost:8000";

export interface SourceCitation {
  source: string;
  reference: string;
  url?: string | null;
}

export interface MedicationRef {
  id: string;
  name: string;
}

export interface SuggestedMedication {
  medicationId: string;
  name: string;
  confidence: number;
}

export interface AlternativeSuggestion {
  text: string;
  citation: SourceCitation;
}

export interface MedicationInfo {
  id: string;
  name: string;
  salts: string[];
  drugClass: string;
  alternatives: AlternativeSuggestion[];
}

export interface DetectedItem {
  input: string;
  recognized: boolean;
  medication: MedicationInfo | null;
  suggestions?: SuggestedMedication[] | null;
}

export type Severity = "high" | "moderate" | "low";

export interface InteractionWarning {
  medications: [MedicationRef, MedicationRef];
  // null iff severityUngraded is true — the source recorded this pair
  // without a grade (see docs/api-contract.md). Still a real finding.
  severity: Severity | null;
  severityUngraded: boolean;
  title: string;
  explanation: string;
  citation: SourceCitation;
}

export type TimingRuleType =
  | "separate_from"
  | "take_with_food"
  | "take_on_empty_stomach"
  | "avoid_alcohol"
  | "monitor";

export interface TimingGuidance {
  medication: MedicationRef;
  ruleType: TimingRuleType;
  offsetMinutes: number | null;
  note: string;
  citation: SourceCitation;
}

export interface AnalyzeResponse {
  items: DetectedItem[];
  interactions: InteractionWarning[];
  // A deliberately small, curated set (see docs/api-contract.md) — a
  // medication missing here means "not yet curated", never "no timing
  // considerations apply". Never render an empty array as a clean bill of
  // health.
  timing: TimingGuidance[];
}

export interface HealthResponse {
  status: "ok" | "degraded" | "down";
}

export class ApiError extends Error {
  status?: number | undefined;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) {
      // FastAPI/Pydantic validation errors come back as a list of objects.
      return body.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ") || response.statusText;
    }
  } catch {
    // response body wasn't JSON — fall through to statusText
  }
  return response.statusText || `Request failed (${response.status})`;
}

export async function analyzeMedications(input: string): Promise<AnalyzeResponse> {
  let idToken: string | null;
  try {
    idToken = await getCurrentIdToken();
  } catch (err) {
    // Firebase's token refresh can throw raw errors (e.g. Safari Private
    // Browsing blocking the IndexedDB persistence it relies on) — wrap so
    // the UI always shows a real reason instead of a generic fallback.
    const message = err instanceof Error ? err.message : String(err);
    throw new ApiError(`Couldn't verify your sign-in: ${message}`, 401);
  }
  if (!idToken) {
    throw new ApiError("You need to sign in before analyzing medications.", 401);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${idToken}`,
      },
      body: JSON.stringify({ input }),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new ApiError(`Couldn't reach the server: ${message}`);
  }

  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return response.json();
}

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`);
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return response.json();
}

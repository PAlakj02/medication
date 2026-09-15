# API Contract — Pill Check / SaltCheck

Derived from a full read of the frontend source (`src/routes/index.tsx`,
`src/lib/med-data.ts`) as of the current `main`. **The frontend currently makes
zero real network calls.** There is no `fetch`, `axios`, or actual
`useQuery`/`useMutation` usage anywhere in `src/` (confirmed by grep across the
whole tree). `QueryClientProvider` is wired up in `src/routes/__root.tsx` but
nothing ever calls `useQuery`. Every "API" is a synchronous, in-memory lookup
against the hardcoded `MEDS` and `RULES` arrays in `src/lib/med-data.ts`, and
the "Analyzing…" loading state is a fake `setTimeout(..., 250)` — not a real
request.

So every endpoint below is **implied**, not observed. Fields are marked:
- **INFERRED** — shape reverse-engineered from the mock data / render logic, not present as an explicit type contract anywhere.
- **NEW** — does not exist in the frontend today at all; added per your decisions below and will require a frontend change to consume.

Decisions confirmed with you (2026-09-05), reflected throughout this doc:
1. **Single combined endpoint** (`POST /api/analyze`) rather than separate `/detect`, `/interactions`, `/alternatives` calls.
2. Unmatched items get an **optional `suggestions` field** (fuzzy-match candidates), not just a hard boolean.
3. Interaction warnings and alternative suggestions **require a `citation` field** — this is a required frontend change (see `frontend-notes.md` §4).
4. Severity stays the existing **enum** (`"high" | "moderate" | "low"`), no numeric score for now.

---

## 0. Auth (added 2026-09-15)

`POST /api/analyze` now requires a Firebase ID token: `Authorization: Bearer <idToken>`.
`GET /api/health` stays open (no token). Backend verifies the token directly
against Google's public certs (`google-auth`'s `verify_firebase_token`,
project id only) — no Admin SDK, no service account secret, and the backend
never calls Firebase's Admin API or stores anything about the user. This is a
pure login gate, consistent with the earlier "no per-user data saved" decision.

Missing/invalid/expired token → `401` with `{"detail": "..."}`.

Frontend: `src/lib/firebase.ts` (Google sign-in popup) + `src/lib/api.ts`'s
`analyzeMedications()`, which attaches the current user's ID token
automatically and throws `ApiError` with status `401` if no one is signed in.

## 1. `POST /api/analyze`

The only endpoint the frontend needs for its current feature set. Triggered by
the Analyze button (`src/routes/index.tsx:139-146`) and by clicking one of the
three example chips (`analyze(ex)`, same code path).

### Request

```typescript
interface AnalyzeRequest {
  /** Raw textarea content, exactly as pasted/typed by the user. */
  input: string;
}
```

Today the frontend pre-splits this itself with `parseInput()`
(`src/lib/med-data.ts:254-259`) on commas, semicolons, or newlines before ever
looking anything up. **Once the backend/ML layer owns detection, that
client-side splitting becomes redundant** — send the raw string as-is and let
the backend's NLP/NER layer do the segmentation. This is the single biggest
behavioral shift the backend introduces; see `frontend-notes.md` §5.

Frontend does `.trim()` and refuses to call at all if the trimmed string is
empty (`disabled={busy || !value.trim()}`), so the backend can assume
non-empty input but should still validate defensively.

### Response

```typescript
interface AnalyzeResponse {
  items: DetectedItem[];
  interactions: InteractionWarning[];
}

interface DetectedItem {
  /** The raw token as the user typed it, e.g. "Ibuprofen" or "asprin 100mg". */
  input: string;
  recognized: boolean;
  medication: MedicationInfo | null;
  /**
   * NEW. Only meaningful when recognized === false. Lets the ML layer
   * surface "did you mean X?" instead of a flat "not recognized" — the
   * frontend has no UI for this yet (see frontend-notes.md §5).
   */
  suggestions?: SuggestedMedication[];
}

interface MedicationInfo {
  /**
   * INFERRED. The mock data has no id — the frontend keys/dedupes purely
   * on `name` (see `detect()`, src/lib/med-data.ts:261-279, and the `key={m.name}`
   * usages in index.tsx). A real backend needs a stable id for joins; the
   * frontend will need to switch its React keys from `name` to `id`.
   */
  id: string;
  name: string;
  /** e.g. ["Acetylsalicylic acid 325mg"]. Rendered as a "·"-joined mono line. */
  salts: string[];
  /**
   * INFERRED rename. Mock field is called `className` (src/lib/med-data.ts:5) —
   * renamed here to avoid colliding with the JS/DOM `className` concept.
   * Rendered as a badge, e.g. "NSAID / Antiplatelet".
   */
  drugClass: string;
  alternatives: AlternativeSuggestion[];
}

interface AlternativeSuggestion {
  /** Free-text today, e.g. "Acetaminophen (Paracetamol) for pain without bleeding risk". */
  text: string;
  /**
   * NEW — required per your decision in §4. The mock `alternatives: string[]`
   * (src/lib/med-data.ts:15 etc.) has zero citation today. This is a
   * clinical recommendation and needs the same sourcing rigor as
   * interaction warnings.
   */
  citation: SourceCitation;
}

interface SuggestedMedication {
  /** NEW. */
  medicationId: string;
  name: string;
  /** 0–1. How confident the fuzzy match is. */
  confidence: number;
}

interface InteractionWarning {
  /**
   * INFERRED. Mock `Rule` type stores this as bare name strings `a`/`b`
   * (src/lib/med-data.ts:127-132), matched against `Med.name`. Promoted to
   * refs with ids for real joins.
   */
  medications: [MedicationRef, MedicationRef];
  /**
   * UPDATED (2026-09-08). One real backend source (DDInter) records ~21% of
   * its interaction pairs without a severity grade at all ("Unknown" in the
   * source data) rather than high/moderate/low. Those are real, sourced
   * interactions — not omitted — so `severity` is nullable and
   * `severityUngraded` tells you which case you're in. The frontend needs a
   * render path for severityUngraded === true that is visually distinct
   * from "no interactions found" — it is NOT the same as an empty/absent
   * warning, and must not be dropped from the worst-severity banner logic
   * silently (an ungraded pair should still surface as "a potential
   * interaction was found, severity unknown", not be invisible).
   */
  severity: "high" | "moderate" | "low" | null;
  /** NEW (2026-09-08). True iff severity is null. */
  severityUngraded: boolean;
  /** Short label, e.g. "Major bleeding risk". */
  title: string;
  /** INFERRED rename of mock's `detail` field — free-text clinical explanation. */
  explanation: string;
  /** NEW — required per your decision in §4. Mock has no citation at all. */
  citation: SourceCitation;
}

interface MedicationRef {
  id: string;
  name: string;
}

interface SourceCitation {
  /** NEW. e.g. "DrugBank", "FDA label", "PubMed". */
  source: string;
  /** e.g. a DrugBank ID, PMID, or FDA label section identifier. */
  reference: string;
  url?: string;
}
```

### Behavior notes carried over from the mock implementation

- **Dedup**: the frontend's `detect()` dedupes by recognized medication name
  (or by the raw normalized token if unrecognized) — if the same medication is
  mentioned twice, it appears once in `items` (`src/lib/med-data.ts:272-277`).
  Preserve this or the "Detected items" count badge and list will show
  duplicates the current UI never has to handle.
- **Interactions are computed over the set of recognized medications, not
  per-input-token** — `findInteractions()` takes the deduped set of `known`
  medications and returns every rule where *both* sides are present
  (`src/lib/med-data.ts:281-284`, called at `index.tsx:68`). A given
  `InteractionWarning` is not tied to a specific `DetectedItem` index.
- **Worst-severity banner** ("High risk detected" / "No known interactions" /
  "Add more items to compare") is derived client-side by scanning
  `interactions` for the highest severity present (`index.tsx:69-75`). This is
  a trivial reducer — fine to leave client-side — but it depends on the
  severity enum staying exactly `"high" | "moderate" | "low"` with that
  precedence order. **UPDATED (2026-09-08)**: this reducer needs a fourth
  case now — an `interactions` array can be non-empty while containing only
  `severityUngraded: true` entries (severity `null`). Today's reducer
  (`i.severity === "high"` etc.) would silently treat those as neither
  matching nor absent and fall through oddly; it needs an explicit branch,
  not just wider typing.
- **Unrecognized items still render**, just without a `medication` — the "Not
  recognized in our database" card (`index.tsx:183-190`). Don't omit
  unmatched tokens from `items`.

---

## 2. `GET /api/health` — recommended addition, not currently called

The header's "Engine online" status pill (`index.tsx:101-108`) is **entirely
static** — a hardcoded green dot with `animate-ping`, not wired to any request
or state at all. It is misleading in its current form since it will say
"Engine online" even if the backend is down.

This isn't something the frontend implies today (there's no polling, no
fetch), but I'd recommend adding a real health check now, since a wiring bug
here is cheap to introduce and expensive to notice (a false "online" during a
real outage). Frontend would need a small `useQuery`/`useEffect` addition to
consume it — flagged in `frontend-notes.md` §5.

```typescript
interface HealthResponse {
  status: "ok" | "degraded" | "down";
}
```

---

## Error handling — undefined today, needs a decision before backend integration

The frontend has **no error-handling path whatsoever**. `analyze()`
(`index.tsx:77-86`) never fails — it's a client-side `setTimeout`, not a
request, so there is no try/catch, no error state variable, and no rendered
error UI anywhere in the component. `sonner` (a toast library) is installed as
a dependency but never imported or used.

This means integrating a real backend requires **new frontend work**
regardless of what the backend does: a loading state that can fail, and some
UI to show a failure. I'd suggest a standard envelope for actual errors (bad
request, server fault) — but note that "zero medications recognized" is *not*
an error, it's a valid `AnalyzeResponse` with an empty/all-unrecognized
`items` list, exactly like today's "Not recognized in our database" case.

```typescript
interface ErrorResponse {
  error: {
    code: string;
    message: string;
  };
}
```

Flagging this as open rather than guessing further — happy to firm this up
once the backend's real failure modes (timeout, ML service down, malformed
input) are clearer.

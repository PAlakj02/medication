# Frontend Notes — Pill Check / SaltCheck

Companion to `docs/api-contract.md`. Covers structure, state, routing, and the
assumptions baked into the current frontend that will constrain backend
integration.

## 1. Component tree

```
RootShell                          (src/routes/__root.tsx — <html>/<head>/<body>, HeadContent, Scripts)
└─ RootComponent
   └─ QueryClientProvider          (react-query is installed and wired up, but
      │                             ZERO components anywhere call useQuery/
      │                             useMutation — confirmed via grep. Likely
      │                             template scaffolding for future use.)
      └─ <Outlet/>
         ├─ NotFoundComponent      (404, __root.tsx:15-35)
         ├─ ErrorComponent         (route error boundary, __root.tsx:37-73;
         │                          reports to window.__lovableEvents, a
         │                          Lovable-editor-only telemetry hook — dead
         │                          code outside the Lovable preview iframe)
         └─ Index                  (src/routes/index.tsx — the ONLY route/page)
            ├─ header (inline JSX, not extracted)
            │   ├─ logo + "SaltCheck" title
            │   └─ "Engine online" status pill (STATIC — not wired to anything)
            ├─ input section (inline JSX)
            │   ├─ Textarea (shadcn/ui)
            │   ├─ Button "Analyze" (shadcn/ui)
            │   └─ example chips (EXAMPLES constant, 3 hardcoded strings)
            ├─ results section — only rendered when `submitted` is truthy
            │   ├─ "Detected items" card       → CardHeader + <ul> of DetectedItem
            │   ├─ "Interactions & safety" card → CardHeader + severity banner + <ul> of InteractionWarning
            │   └─ "Alternatives" card          → CardHeader + <ul> of (medication → alternatives)
            └─ static disclaimer footer (not medical advice)
```

`CardHeader` (icon + title + count badge, `index.tsx:282-302`) is the only
extracted local component; everything else in `Index` is inline JSX. There is
no component library specific to this feature beyond generic shadcn/ui
primitives in `src/components/ui/*` (accordion, dialog, table, etc.) — almost
none of which are actually used by `Index` today; they're template
boilerplate available for future screens.

## 2. State management

- **No global store** (no Redux/Zustand/Context for app data). `QueryClient`
  exists but holds no queries.
- All state is local to `Index` via `useState`:
  - `value: string` — live textarea content.
  - `submitted: string | null` — the last string actually analyzed (`null`
    until the first Analyze click); gates whether the results section renders
    at all.
  - `busy: boolean` — true for the fake 250ms `setTimeout` window; drives the
    "Analyzing…" button label and the disabled state.
- **Derived data via `useMemo`**, recomputed from `submitted`:
  - `detected` ← `detect(submitted)`
  - `known` ← `detected` filtered to non-null `.med`
  - `interactions` ← `findInteractions(known)`
  - `worst` — *not* memoized, just an inline expression scanning `interactions`
    for the highest severity present, each render.
- **No persistence of any kind** — no URL query param, no localStorage, no
  server cache. A page refresh loses the input and results entirely. There is
  no "history of past analyses" concept anywhere in the UI.
- **No auth/session/user identity** anywhere in the app. Every analysis is
  anonymous and stateless.

## 3. Routing

- TanStack Start file-based routing (conventions documented in
  `src/routes/README.md`).
- **Exactly one route exists**: `index.tsx` → `/`. No dynamic segments, no
  nested routes, no route-level data loaders, no auth-gated routes.
- `__root.tsx` is the single app shell wrapping every route (head tags, fonts,
  global CSS import, 404/error boundaries).
- `routeTree.gen.ts` is auto-generated — don't hand-edit; regenerates from the
  `src/routes/` file tree.

## 4. Clinical-judgment surfaces — what the backend must supply to render them

Every place the frontend renders something that is, in substance, a clinical
call (not just a database lookup) is listed here with the exact fields it
needs. This is the list from task item 4.

### a. Interaction warning card (`index.tsx:197-244`)

Renders, per interaction: a severity dot + badge, the two medication names
("`{i.a} + {i.b}`"), a short `title`, and a longer free-text `detail`. Today
**there is no source citation anywhere in this card or the underlying mock
data** (`RULES` array, `src/lib/med-data.ts:134-248`) — it's just an
engineer-authored string. Per your decision in `api-contract.md`, the real
backend response must add a `citation` field here, which means:
- **Required fields to render today**: `severity`, `title`, `explanation`
  (mock's `detail`), the two medication names.
- **Required NEW field**: `citation` (source name + reference/URL) — **the
  frontend does not yet have a UI slot for this and will need one** (e.g. a
  small "Source: DrugBank ⧉" link under the explanation text). Flagging this
  explicitly as a required frontend follow-up, not optional polish.

### b. Severity banner (`index.tsx:203-223`)

The "High risk detected" / "No known interactions" / "Add more items to
compare" summary at the top of the interactions card is a triage judgment
rendered as the primary visual signal on the page. It only needs the
aggregate `worst` severity plus a count — both derivable client-side from the
`interactions` array, no new backend field required, but it depends on
severity being a stable, totally-ordered enum (see contract note on this).

### c. Alternatives card (`index.tsx:246-268`)

For each recognized medication, renders a bare list of free-text alternative
suggestions (`m.alternatives`, e.g. "Escitalopram (similar class, different
metabolism)"). This is a clinical recommendation exactly like an interaction
warning, but today it carries **no severity, no rationale beyond the string
itself, and no citation at all**. Per your decision, this also needs a
`citation` per alternative — again, **no frontend UI slot exists yet**.

### d. Implicit judgment in detection itself

Deciding whether a user's raw token maps to a known medication is itself a
judgment call with real safety consequences: a false negative (real med not
recognized) silently skips interaction checking for it, with no warning to
the user beyond an easy-to-miss "Not recognized in our database" note
(`index.tsx:183-190`). Today this is a hard boolean with no confidence
signal. Your decision to add optional `suggestions` (§ api-contract.md) is a
partial mitigation — the frontend will need new UI to surface "did you mean
X?" and let the user confirm/correct rather than silently proceeding with an
unrecognized token.

## 5. Assumptions baked into the frontend that constrain the backend

1. **Single request/response, no streaming.** One Analyze click = one round
   trip today (a synchronous function call, but the UX contract — button
   disables, then flips to results — implies the same for a real request). If
   the ML layer is slow, there's no incremental/progressive rendering to fall
   back on; the frontend would need a real loading skeleton to replace the
   current fake 250ms delay.
2. **No pagination or virtualization.** `items` and `interactions` render as
   full unvirtualized lists. Fine for a handful of medications; untested for
   someone pasting a very long prescription list.
3. **No error-state UI at all** (see `api-contract.md`'s Error Handling
   section) — integrating any real backend requires adding this to the
   frontend regardless of backend design.
4. **No auth, no session, no history.** If the backend/product direction
   wants saved analyses or accounts, that is entirely new frontend surface,
   not a gap in existing plumbing.
5. **No configured API base URL anywhere** — `import.meta.env` is unused in
   the whole codebase. Wiring in a real backend needs this introduced.
6. **Client-side parsing and matching logic becomes dead code once the
   backend ships.** `parseInput()`, `detect()`, `findInteractions()`, and the
   `MEDS`/`RULES` arrays in `src/lib/med-data.ts` are the entire "product" of
   this app today. Once `POST /api/analyze` is live, this file should be
   deleted rather than kept in parallel — don't let it linger as a second,
   drifting source of truth.
7. **The "Engine online" pill is decorative**, not a real health check
   (`api-contract.md` §2) — worth fixing alongside backend integration so it
   doesn't lie during an outage.
8. **The disclaimer footer is static text**, not conditioned on any response
   field — no backend involvement needed, leave as-is.

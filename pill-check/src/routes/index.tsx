import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Camera,
  CheckCircle2,
  Clock,
  HelpCircle,
  Info,
  LogOut,
  Pill,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  analyzeMedications,
  checkHealth,
  ApiError,
  type AnalyzeResponse,
  type MedicationInfo,
  type Severity,
} from "@/lib/api";
import { onAuthChange, signInWithEmail, signOut, signUpWithEmail, type User } from "@/lib/firebase";
import { extractTextFromImage, OcrError } from "@/lib/ocr";
import { SiteFooter } from "@/components/site-footer";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "SaltCheck — Medication & Supplement Safety Analyzer" },
      {
        name: "description",
        content:
          "Paste your medications and supplements to instantly see active salts, interaction warnings, and safer alternatives.",
      },
      { property: "og:title", content: "SaltCheck — Medication & Supplement Safety Analyzer" },
      {
        property: "og:description",
        content:
          "Instant salt-level interaction checks for medicines and supplements, with safer alternatives.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

const EXAMPLES = [
  "Aspirin, Ibuprofen, Fish Oil",
  "Warfarin, Ginkgo Biloba, Vitamin E",
  "Lisinopril, Potassium, Ibuprofen",
];

type SeverityKey = Severity | "ungraded";

const severityStyles: Record<SeverityKey, { chip: string; dot: string; label: string }> = {
  high: { chip: "bg-danger/10 text-danger", dot: "bg-danger", label: "High" },
  moderate: { chip: "bg-warning/15 text-warning-foreground", dot: "bg-warning", label: "Moderate" },
  low: { chip: "bg-primary/10 text-primary", dot: "bg-primary", label: "Low" },
  ungraded: { chip: "bg-secondary text-secondary-foreground", dot: "bg-secondary-foreground/60", label: "Ungraded" },
};

const gradedRank: Record<Severity, number> = { low: 0, moderate: 1, high: 2 };

const TIMING_RULE_LABELS: Record<string, string> = {
  separate_from: "Take apart from certain other medications",
  take_with_food: "Take with food",
  take_on_empty_stomach: "Take on an empty stomach",
  avoid_alcohol: "Avoid alcohol",
  monitor: "Needs monitoring",
};

const KNOWN_AUTH_ERROR_MESSAGES: Record<string, string> = {
  "auth/operation-not-allowed":
    "Email/password sign-in isn't enabled for this project yet. Enable it in the Firebase console under Authentication → Sign-in method → Email/Password.",
  "auth/email-already-in-use": "An account already exists with this email. Try signing in instead.",
  "auth/invalid-email": "That doesn't look like a valid email address.",
  "auth/weak-password": "Password must be at least 6 characters.",
  "auth/invalid-credential": "Incorrect email or password.",
  "auth/wrong-password": "Incorrect email or password.",
  "auth/user-not-found": "No account found with this email. Try creating one instead.",
  "auth/too-many-requests": "Too many attempts. Please wait a moment and try again.",
};

function describeAuthError(err: unknown): string {
  const code = (err as { code?: string })?.code ?? "unknown";
  // Always include the real code, even when we don't have a friendlier
  // message for it — a blanket "try again" with no code is undebuggable
  // without dev tools.
  return `${KNOWN_AUTH_ERROR_MESSAGES[code] ?? "Sign-in failed."} (${code})`;
}

function worstSeverity(interactions: AnalyzeResponse["interactions"]): SeverityKey | null {
  const graded = interactions.filter((i): i is typeof i & { severity: Severity } => i.severity !== null);
  if (graded.length > 0) {
    return graded.reduce<Severity>(
      (acc, i) => (gradedRank[i.severity] > gradedRank[acc] ? i.severity : acc),
      "low",
    );
  }
  if (interactions.some((i) => i.severityUngraded)) return "ungraded";
  return null;
}

type Status = "idle" | "loading" | "success" | "error";
type AuthStatus = "checking" | "signed-out" | "signed-in";

function Index() {
  const [authStatus, setAuthStatus] = useState<AuthStatus>("checking");
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authSubmitting, setAuthSubmitting] = useState(false);
  const [signInError, setSignInError] = useState<string | null>(null);

  useEffect(() => {
    return onAuthChange((u) => {
      setUser(u);
      setAuthStatus(u ? "signed-in" : "signed-out");
    });
  }, []);

  const submitAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setSignInError(null);
    setAuthSubmitting(true);
    try {
      if (authMode === "sign-up") {
        await signUpWithEmail(email, password);
      } else {
        await signInWithEmail(email, password);
      }
    } catch (err) {
      setSignInError(describeAuthError(err));
    } finally {
      setAuthSubmitting(false);
    }
  };

  if (authStatus === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (authStatus === "signed-out") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background px-5">
        <div className="flex flex-col items-center gap-2 text-center">
          <span className="flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ShieldCheck className="size-5" />
          </span>
          <h1 className="text-lg font-bold text-foreground">SaltCheck</h1>
          <p className="max-w-xs text-xs text-muted-foreground">
            {authMode === "sign-up" ? "Create an account" : "Sign in"} to analyze your medications and
            supplements for interactions.
          </p>
        </div>

        <form onSubmit={submitAuth} className="flex w-full max-w-xs flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email" className="text-xs">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password" className="text-xs">
              Password
            </Label>
            <Input
              id="password"
              type="password"
              autoComplete={authMode === "sign-up" ? "new-password" : "current-password"}
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 6 characters"
            />
          </div>
          <Button
            type="submit"
            disabled={authSubmitting}
            className="bg-cta font-bold text-cta-foreground shadow-sm hover:bg-cta/90"
          >
            {authSubmitting ? "Please wait…" : authMode === "sign-up" ? "Create account" : "Sign in"}
          </Button>
          {signInError && <p className="text-xs text-danger">{signInError}</p>}
        </form>

        <button
          type="button"
          onClick={() => {
            setAuthMode((m) => (m === "sign-up" ? "sign-in" : "sign-up"));
            setSignInError(null);
          }}
          className="text-xs text-muted-foreground underline-offset-2 hover:underline"
        >
          {authMode === "sign-up" ? "Already have an account? Sign in" : "Need an account? Create one"}
        </button>

        <p className="max-w-xs text-center text-[11px] text-muted-foreground/80">
          We only use this to identify you. No medication data is stored or linked to your account.
        </p>
      </div>
    );
  }

  return <Analyzer user={user} />;
}

function Analyzer({ user }: { user: User | null }) {
  const [value, setValue] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [health, setHealth] = useState<"checking" | "ok" | "degraded" | "down">("checking");
  const [ocrReading, setOcrReading] = useState(false);
  const [ocrError, setOcrError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    checkHealth()
      .then((r) => setHealth(r.status))
      .catch(() => setHealth("down"));
  }, []);

  const handleImageSelected = async (file: File) => {
    setOcrError(null);
    setOcrReading(true);
    try {
      const text = await extractTextFromImage(file);
      if (!text) {
        setOcrError("Couldn't find any readable text in that image — try a clearer, well-lit photo.");
        return;
      }
      setValue((prev) => (prev.trim() ? `${prev.trim()}\n${text}` : text));
    } catch (err) {
      setOcrError(err instanceof OcrError ? err.message : "Couldn't read that image. Please try again.");
    } finally {
      setOcrReading(false);
    }
  };

  const detected = result?.items ?? [];
  const known = useMemo(
    () => detected.map((d) => d.medication).filter((m): m is MedicationInfo => m !== null),
    [detected],
  );
  const interactions = result?.interactions ?? [];
  const worst = useMemo(() => worstSeverity(interactions), [interactions]);
  const timing = result?.timing ?? [];

  const analyze = async (text?: string) => {
    const input = (text ?? value).trim();
    if (!input) return;
    setValue(input);
    setStatus("loading");
    setErrorMessage(null);
    try {
      const data = await analyzeMedications(input);
      setResult(data);
      setStatus("success");
    } catch (err) {
      setResult(null);
      setStatus("error");
      setErrorMessage(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b border-border bg-background/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-3 gap-y-2 px-5 py-3">
          <div className="flex items-center gap-2.5">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <ShieldCheck className="size-4" />
            </span>
            <div className="leading-tight">
              <h1 className="text-sm font-bold text-foreground">SaltCheck</h1>
              <p className="hidden text-[11px] text-muted-foreground sm:block">
                Medication & supplement analyzer
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 rounded-full border border-border/60 bg-card px-2 py-0.5 text-[10px] font-medium text-muted-foreground/80">
              <span className="relative flex size-1.5 shrink-0">
                <span
                  className={`absolute inline-flex size-1.5 animate-ping rounded-full ${
                    health === "ok" ? "bg-success/30" : "bg-danger/30"
                  }`}
                />
                <span
                  className={`relative inline-flex size-1.5 rounded-full ${
                    health === "ok" ? "bg-success/60" : "bg-danger/60"
                  }`}
                />
              </span>
              <span className="hidden sm:inline">
                {health === "checking" ? "Checking engine…" : health === "ok" ? "Engine online" : "Engine offline"}
              </span>
            </div>
            {user?.email && (
              <span className="hidden max-w-[10rem] truncate text-[11px] text-muted-foreground md:inline">
                {user.email}
              </span>
            )}
            <button
              type="button"
              onClick={() => signOut()}
              className="flex shrink-0 items-center gap-1 rounded-md border border-border/60 px-2 py-1 text-[11px] text-muted-foreground transition-colors hover:bg-secondary/60"
            >
              <LogOut className="size-3" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-5 pb-10 pt-5">
        <section className="flex flex-col gap-0.5 pb-3">
          <h2 className="text-base font-semibold tracking-tight text-foreground">
            Analyze medications & supplements
          </h2>
          <p className="text-xs text-muted-foreground">
            Paste a list of medicines and supplements to break down active salts, flag interactions,
            and see safer alternatives.
          </p>
        </section>

        <section className="card-surface p-4">
          <label htmlFor="meds" className="sr-only">
            Your list
          </label>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
            <div className="flex flex-1 items-start gap-3">
              <Search className="mt-2.5 size-4 shrink-0 text-muted-foreground" />
              <Textarea
                id="meds"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) analyze();
                }}
                placeholder={`e.g. Aspirin, Ibuprofen, Fish Oil\nOr paste a multi-line prescription list`}
                className="min-h-[96px] flex-1 resize-none border-0 bg-transparent px-0 py-3 text-sm leading-snug text-foreground shadow-none placeholder:text-muted-foreground/70 focus-visible:ring-0"
                rows={4}
              />
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) handleImageSelected(file);
              }}
            />
            <div className="flex shrink-0 items-center gap-2 self-end sm:self-start">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={ocrReading}
                onClick={() => fileInputRef.current?.click()}
                className="shrink-0"
                title="Scan text from a photo of packaging or a label"
              >
                <Camera className="size-4" />
              </Button>
              <Button
                onClick={() => analyze()}
                disabled={status === "loading" || !value.trim()}
                size="sm"
                className="shrink-0 bg-cta font-bold text-cta-foreground shadow-sm hover:bg-cta/90"
              >
                {status === "loading" ? "Analyzing…" : "Analyze"}
              </Button>
            </div>
          </div>
          {ocrReading && (
            <p className="mt-2 text-[11px] text-muted-foreground">Reading text from image…</p>
          )}
          {ocrError && <p className="mt-2 text-[11px] text-danger">{ocrError}</p>}
          <div className="mt-3 flex flex-wrap items-center gap-1.5 pt-2">
            <span className="text-[11px] text-muted-foreground">Try:</span>
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => analyze(ex)}
                className="rounded-md border border-transparent bg-chip px-2 py-0.5 text-[11px] text-chip-foreground transition-colors hover:border-primary/40 hover:bg-primary/5"
              >
                {ex}
              </button>
            ))}
          </div>
        </section>

        {status === "error" && (
          <section className="mt-4 card-surface border border-danger/30 bg-danger/5 p-4">
            <div className="flex items-start gap-2 text-danger">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              <div>
                <p className="text-sm font-semibold">Couldn't analyze your list</p>
                <p className="text-[11px] opacity-80">{errorMessage}</p>
              </div>
            </div>
          </section>
        )}

        {status === "success" && result && (
          <section className="mt-5 grid gap-4 lg:grid-cols-3">
            <div className="card-surface p-4">
              <CardHeader icon={<Pill className="size-4" />} title="Detected items" count={detected.length} />
              <ul className="mt-3 space-y-2">
                {detected.map((d) => (
                  <li key={d.input} className="rounded-lg border border-border/70 bg-secondary/40 p-2.5">
                    {d.medication ? (
                      <>
                        <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
                          <span className="min-w-0 break-words text-sm font-semibold text-foreground">
                            {d.medication.name}
                          </span>
                          <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                            {d.medication.drugClass}
                          </span>
                        </div>
                        <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                          {d.medication.salts.join(" · ")}
                        </p>
                      </>
                    ) : (
                      <div className="flex items-start gap-2">
                        <HelpCircle className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                        <div>
                          <p className="text-sm font-semibold text-foreground">{d.input}</p>
                          <p className="text-[11px] text-muted-foreground">Not recognized in our database</p>
                          {d.suggestions && d.suggestions.length > 0 && (
                            <p className="mt-1 text-[11px] text-muted-foreground">
                              Did you mean: {d.suggestions.map((s) => s.name).join(", ")}?
                            </p>
                          )}
                        </div>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>

            <div className="card-surface p-4">
              <CardHeader
                icon={<Activity className="size-4" />}
                title="Interactions & safety"
                count={interactions.length}
              />
              <div
                className={`mt-3 flex items-start gap-3 rounded-lg p-2.5 ${
                  worst ? severityStyles[worst].chip : "bg-success/10 text-success"
                }`}
              >
                {worst ? <AlertTriangle className="mt-0.5 size-4 shrink-0" /> : <CheckCircle2 className="mt-0.5 size-4 shrink-0" />}
                <div>
                  <p className="text-sm font-semibold">
                    {worst
                      ? worst === "ungraded"
                        ? "Ungraded interaction found"
                        : `${severityStyles[worst].label} risk detected`
                      : known.length > 1
                        ? "No known interactions"
                        : "Add more items to compare"}
                  </p>
                  <p className="text-[11px] opacity-80">
                    {worst
                      ? `${interactions.length} potential salt interaction${interactions.length > 1 ? "s" : ""} found.`
                      : "Nothing flagged between the recognized items."}
                  </p>
                </div>
              </div>

              <ul className="mt-3 space-y-2">
                {interactions.map((i) => {
                  const key: SeverityKey = i.severityUngraded ? "ungraded" : (i.severity as Severity);
                  const style = severityStyles[key];
                  return (
                    <li
                      key={`${i.medications[0].id}-${i.medications[1].id}`}
                      className="rounded-lg border border-border/70 p-2.5"
                    >
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span className={`size-1.5 shrink-0 rounded-full ${style.dot}`} />
                        <span className="min-w-0 flex-1 break-words text-sm font-semibold text-foreground">
                          {i.medications[0].name} + {i.medications[1].name}
                        </span>
                        <span
                          className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${style.chip}`}
                        >
                          {style.label}
                        </span>
                      </div>
                      <p className="mt-1 text-xs font-medium text-foreground">{i.title}</p>
                      <p className="mt-1 text-[11px] text-muted-foreground">{i.explanation}</p>
                      <p className="mt-1 text-[10px] text-muted-foreground/80">
                        Source:{" "}
                        {i.citation.url ? (
                          <a
                            href={i.citation.url}
                            target="_blank"
                            rel="noreferrer"
                            className="underline hover:text-foreground"
                          >
                            {i.citation.source}
                          </a>
                        ) : (
                          i.citation.source
                        )}
                      </p>
                    </li>
                  );
                })}
              </ul>
            </div>

            <div className="card-surface p-4">
              <CardHeader icon={<Sparkles className="size-4" />} title="Alternatives" count={known.length} />
              <ul className="mt-3 space-y-2">
                {known.map((m) => (
                  <li key={m.id} className="rounded-lg border border-border/70 p-2.5">
                    <p className="text-sm font-semibold text-foreground">{m.name}</p>
                    <ul className="mt-1.5 space-y-1">
                      {m.alternatives.map((alt, idx) => (
                        <li key={idx} className="flex gap-2 text-[11px] text-muted-foreground">
                          <span className="mt-1.5 size-1 shrink-0 rounded-full bg-primary" />
                          {alt.text}
                        </li>
                      ))}
                      {m.alternatives.length === 0 && (
                        <li className="text-[11px] text-muted-foreground/70">No alternatives available yet.</li>
                      )}
                    </ul>
                  </li>
                ))}
                {known.length === 0 && (
                  <li className="text-[11px] text-muted-foreground">
                    No recognized items yet — try one of the examples above.
                  </li>
                )}
              </ul>
            </div>
          </section>
        )}

        {status === "success" && known.length > 0 && (
          <section className="mt-4 card-surface p-4">
            <CardHeader icon={<Clock className="size-4" />} title="Dosing & timing" count={timing.length} />
            <ul className="mt-3 space-y-2">
              {known.map((m) => {
                const rulesForMed = timing.filter((t) => t.medication.id === m.id);
                return (
                  <li key={m.id} className="rounded-lg border border-border/70 p-2.5">
                    <p className="text-sm font-semibold text-foreground">{m.name}</p>
                    {rulesForMed.length > 0 ? (
                      <ul className="mt-1.5 space-y-2">
                        {rulesForMed.map((rule, idx) => (
                          <li key={idx}>
                            <p className="text-xs font-medium text-foreground">
                              {TIMING_RULE_LABELS[rule.ruleType] ?? rule.ruleType}
                            </p>
                            <p className="text-[11px] text-muted-foreground">{rule.note}</p>
                            <p className="mt-0.5 text-[10px] text-muted-foreground/80">
                              Source:{" "}
                              {rule.citation.url ? (
                                <a
                                  href={rule.citation.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="underline hover:text-foreground"
                                >
                                  {rule.citation.source}
                                </a>
                              ) : (
                                rule.citation.source
                              )}
                            </p>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-1 text-[11px] text-muted-foreground/70">
                        No specific timing guidance in our data — check with your pharmacist.
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        <p className="mx-auto mt-6 flex max-w-2xl items-start gap-2 text-[11px] text-foreground/80">
          <Info className="mt-0.5 size-3.5 shrink-0" />
          SaltCheck is an informational tool and not medical advice. Always confirm with a pharmacist
          or physician before changing any medication.
        </p>
      </main>
      <SiteFooter />
    </div>
  );
}

function CardHeader({
  icon,
  title,
  count,
}: {
  icon: React.ReactNode;
  title: string;
  count: number;
}) {
  return (
    <div className="flex items-center gap-2 border-b border-border/70 pb-2.5">
      <span className="flex size-6 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
        {icon}
      </span>
      <h3 className="text-sm font-bold text-foreground">{title}</h3>
      <span className="ml-auto rounded-full bg-secondary px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">
        {count}
      </span>
    </div>
  );
}

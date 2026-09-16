import { Link } from "@tanstack/react-router";
import { LogOut, ShieldCheck } from "lucide-react";

interface AppHeaderProps {
  health?: "checking" | "ok" | "degraded" | "down";
  onSignOut?: () => void;
}

const NAV_LINKS = [
  { to: "/about", label: "About" },
  { to: "/terms", label: "Terms & Privacy" },
  { to: "/contact", label: "Contact" },
];

// Shared across every page (login screen, analyzer, about/terms/contact) so
// nav and branding stay consistent everywhere, not just inside the app.
// Two rows on purpose: cramming branding + nav + health/sign-out into one
// row broke down on narrow screens (three groups fighting for space with
// no wrap handling). Splitting nav onto its own row keeps every row simple
// enough to never need to shrink below readable size.
export function AppHeader({ health, onSignOut }: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-10 border-b border-border bg-background/90 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-5 pt-3">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ShieldCheck className="size-4" />
          </span>
          <div className="leading-tight">
            <h1 className="text-sm font-bold text-foreground">SaltCheck</h1>
            <p className="hidden text-[11px] text-muted-foreground sm:block">
              Medication & supplement analyzer
            </p>
          </div>
        </Link>

        <div className="flex shrink-0 items-center gap-2">
          {health && (
            <div className="hidden items-center gap-2 rounded-full border border-border/60 bg-card px-2 py-0.5 text-[10px] font-medium text-muted-foreground/80 sm:flex">
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
              {health === "checking" ? "Checking engine…" : health === "ok" ? "Engine online" : "Engine offline"}
            </div>
          )}
          {onSignOut && (
            <button
              type="button"
              onClick={onSignOut}
              className="flex shrink-0 items-center gap-1 rounded-md border border-border/60 px-2 py-1 text-[11px] text-muted-foreground transition-colors hover:bg-secondary/60"
            >
              <LogOut className="size-3" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          )}
        </div>
      </div>

      <nav className="mx-auto flex max-w-5xl items-center justify-center gap-4 px-5 py-2 text-[11px] font-medium text-muted-foreground sm:justify-end">
        {NAV_LINKS.map((l) => (
          <Link key={l.to} to={l.to} className="hover:text-foreground hover:underline [&.active]:text-foreground">
            {l.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}

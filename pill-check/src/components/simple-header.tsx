import { Link } from "@tanstack/react-router";
import { ShieldCheck } from "lucide-react";

export function SimpleHeader() {
  return (
    <header className="border-b border-border">
      <div className="mx-auto flex max-w-3xl items-center justify-between px-5 py-3">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ShieldCheck className="size-4" />
          </span>
          <div className="leading-tight">
            <h1 className="text-sm font-bold text-foreground">SaltCheck</h1>
            <p className="text-[11px] text-muted-foreground">Medication & supplement analyzer</p>
          </div>
        </Link>
        <Link to="/" className="text-xs font-medium text-primary hover:underline">
          Back to app
        </Link>
      </div>
    </header>
  );
}

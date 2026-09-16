import { createFileRoute } from "@tanstack/react-router";
import { Mail } from "lucide-react";

import { SimpleHeader } from "@/components/simple-header";
import { SiteFooter } from "@/components/site-footer";

export const Route = createFileRoute("/contact")({
  head: () => ({
    meta: [
      { title: "Contact — SaltCheck" },
      { name: "description", content: "Get in touch about SaltCheck." },
    ],
  }),
  component: Contact,
});

// PLACEHOLDER — replace once the real domain/inbox exists.
const CONTACT_EMAIL = "hello@saltcheck.app";

function Contact() {
  return (
    <div className="min-h-screen bg-background">
      <SimpleHeader />
      <main className="mx-auto max-w-3xl px-5 py-8">
        <h1 className="text-xl font-bold text-foreground">Contact us</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Questions, feedback, or found something in our data that looks wrong? We'd like to
          hear about it.
        </p>

        <a
          href={`mailto:${CONTACT_EMAIL}`}
          className="mt-5 inline-flex items-center gap-2 rounded-md bg-cta px-4 py-2 text-sm font-bold text-cta-foreground shadow-sm transition-colors hover:bg-cta/90"
        >
          <Mail className="size-4" />
          {CONTACT_EMAIL}
        </a>

        <p className="mt-6 text-[11px] text-muted-foreground">
          We don't run a support form here on purpose — we don't want to collect and store
          messages when a plain email works just as well. See our{" "}
          <a href="/terms" className="text-primary hover:underline">
            Terms & Privacy
          </a>{" "}
          page for more on how we handle data.
        </p>
      </main>
      <SiteFooter />
    </div>
  );
}

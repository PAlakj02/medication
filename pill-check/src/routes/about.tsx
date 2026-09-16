import { createFileRoute } from "@tanstack/react-router";

import { SimpleHeader } from "@/components/simple-header";
import { SiteFooter } from "@/components/site-footer";

export const Route = createFileRoute("/about")({
  head: () => ({
    meta: [
      { title: "About — SaltCheck" },
      {
        name: "description",
        content: "What SaltCheck is, how it checks medication interactions, and where its data comes from.",
      },
    ],
  }),
  component: About,
});

function About() {
  return (
    <div className="min-h-screen bg-background">
      <SimpleHeader />
      <main className="mx-auto max-w-3xl px-5 py-8">
        <h1 className="text-xl font-bold text-foreground">About SaltCheck</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          SaltCheck helps you check whether the medications and supplements you're taking might
          interact, and surfaces basic dosing-timing guidance where we have it.
        </p>

        <div className="mt-6 space-y-5 text-sm text-foreground">
          <section>
            <h2 className="font-semibold">How it works</h2>
            <p className="mt-1 text-muted-foreground">
              SaltCheck never lets an AI model decide whether an interaction exists. Every
              interaction warning comes from a deterministic lookup against real, sourced
              interaction data (currently{" "}
              <a href="http://ddinter.scbdd.com/" target="_blank" rel="noreferrer" className="text-primary hover:underline">
                DDInter
              </a>
              ) — an AI model is only used afterward, to rephrase an already-established finding
              into plain language. It's never allowed to invent a finding, a severity, or a
              mechanism on its own.
            </p>
          </section>

          <section>
            <h2 className="font-semibold">Where the data comes from</h2>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-muted-foreground">
              <li>Ingredient and product names — RxNorm (US National Library of Medicine)</li>
              <li>Interaction data — DDInter</li>
              <li>Dosing-timing guidance — real FDA/DailyMed drug labels, cited individually</li>
            </ul>
          </section>

          <section>
            <h2 className="font-semibold">What it can't do</h2>
            <p className="mt-1 text-muted-foreground">
              Our data doesn't cover every medication or every possible interaction. When we
              genuinely don't have data for something, we say so explicitly rather than implying
              it's safe. This tool is informational only and does not replace advice from a
              pharmacist or physician — see our{" "}
              <a href="/terms" className="text-primary hover:underline">
                Terms & Privacy
              </a>{" "}
              page.
            </p>
          </section>

          <section>
            <h2 className="font-semibold">Your data</h2>
            <p className="mt-1 text-muted-foreground">
              We don't store what medications you look up. Signing in only identifies you to use
              the app — it isn't linked to any medication data.
            </p>
          </section>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}

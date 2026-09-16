import { createFileRoute } from "@tanstack/react-router";

import { AppHeader } from "@/components/app-header";
import { SiteFooter } from "@/components/site-footer";

export const Route = createFileRoute("/terms")({
  head: () => ({
    meta: [
      { title: "Terms & Privacy — SaltCheck" },
      { name: "description", content: "SaltCheck's terms of use and privacy practices." },
    ],
  }),
  component: Terms,
});

function Terms() {
  return (
    <div className="min-h-screen bg-background">
      <AppHeader />
      <main className="mx-auto max-w-3xl px-5 py-8">
        <h1 className="text-xl font-bold text-foreground">Terms & Privacy</h1>
        <p className="mt-1 text-[11px] text-muted-foreground">
          Last updated 2026-09-16. This is a plain-language draft, not a substitute for legal
          review — please have a lawyer review this before treating it as final.
        </p>

        <div className="mt-6 space-y-5 text-sm text-foreground">
          <section>
            <h2 className="font-semibold">Not medical advice</h2>
            <p className="mt-1 text-muted-foreground">
              SaltCheck is an informational tool, not a medical device, and does not provide
              medical advice, diagnosis, or treatment. Always consult a licensed pharmacist or
              physician before starting, stopping, or changing any medication or supplement.
              Never disregard professional medical advice because of something you see in this
              app.
            </p>
          </section>

          <section>
            <h2 className="font-semibold">Data can be incomplete</h2>
            <p className="mt-1 text-muted-foreground">
              Our interaction and timing data comes from real, cited sources (see{" "}
              <a href="/about" className="text-primary hover:underline">
                About
              </a>
              ), but it does not cover every medication, supplement, or possible interaction. The
              absence of a warning is not proof that a combination is safe — it may simply mean
              we don't have data on it yet.
            </p>
          </section>

          <section>
            <h2 className="font-semibold">Your account and data</h2>
            <p className="mt-1 text-muted-foreground">
              We use sign-in only to identify you as a user of the app. We do not store the
              medications, supplements, or text you enter, and we do not link any medication
              data to your account. Your email address is used solely for authentication.
            </p>
          </section>

          <section>
            <h2 className="font-semibold">Photos you scan</h2>
            <p className="mt-1 text-muted-foreground">
              If you use the camera/photo feature, the image is processed entirely in your own
              browser to extract text — it is not uploaded to our servers or stored anywhere.
            </p>
          </section>

          <section>
            <h2 className="font-semibold">No warranty</h2>
            <p className="mt-1 text-muted-foreground">
              SaltCheck is provided "as is," without warranties of any kind. We do not guarantee
              the accuracy, completeness, or timeliness of any information shown. To the fullest
              extent permitted by law, we are not liable for any decision made based on this
              app's output.
            </p>
          </section>

          <section>
            <h2 className="font-semibold">Changes</h2>
            <p className="mt-1 text-muted-foreground">
              We may update these terms as the app changes. Continued use after an update means
              you accept the revised terms.
            </p>
          </section>

          <section>
            <h2 className="font-semibold">Contact</h2>
            <p className="mt-1 text-muted-foreground">
              Questions about these terms? See our{" "}
              <a href="/contact" className="text-primary hover:underline">
                Contact
              </a>{" "}
              page.
            </p>
          </section>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}

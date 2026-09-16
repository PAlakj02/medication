export function SiteFooter() {
  return (
    <footer className="mx-auto mt-10 max-w-5xl px-5 pb-8">
      <p className="border-t border-border pt-4 text-center text-[11px] text-muted-foreground">
        &copy; {new Date().getFullYear()} SaltCheck
      </p>
    </footer>
  );
}

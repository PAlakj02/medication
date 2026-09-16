import { Link } from "@tanstack/react-router";

export function SiteFooter() {
  return (
    <footer className="mx-auto mt-10 max-w-5xl px-5 pb-8">
      <div className="flex flex-wrap items-center justify-center gap-4 border-t border-border pt-4 text-[11px] text-muted-foreground">
        <Link to="/" className="hover:text-foreground hover:underline">
          Home
        </Link>
        <Link to="/about" className="hover:text-foreground hover:underline">
          About
        </Link>
        <Link to="/terms" className="hover:text-foreground hover:underline">
          Terms & Privacy
        </Link>
        <Link to="/contact" className="hover:text-foreground hover:underline">
          Contact
        </Link>
        <span className="ml-auto">&copy; {new Date().getFullYear()} SaltCheck</span>
      </div>
    </footer>
  );
}

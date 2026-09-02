import Link from "next/link";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";

/**
 * Landing header. Sticky and translucent so the hero image scrolls under it.
 */
export function SiteHeader({ farmerName }: { farmerName?: string }) {
  return (
    <header className="border-border bg-background/80 sticky top-0 z-50 border-b backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-6xl items-center gap-6 px-4 py-3">
        <Logo />

        <nav className="text-muted-foreground hidden items-center gap-6 text-sm md:flex">
          <a href="#problem" className="hover:text-foreground">
            The problem
          </a>
          <a href="#answers" className="hover:text-foreground">
            What you get
          </a>
          <a href="#how" className="hover:text-foreground">
            How it works
          </a>
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {farmerName ? (
            <>
              <span className="text-muted-foreground hidden text-sm sm:inline">
                {farmerName}
              </span>
              <form action="/api/farmer/sign-out" method="post">
                <Button type="submit" variant="ghost" size="sm">
                  Sign out
                </Button>
              </form>
            </>
          ) : (
            <>
              <Button asChild variant="ghost" size="sm">
                <Link href="/login">Farmer sign in</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/depot/sign-in">Depot officer</Link>
              </Button>
            </>
          )}
          <Button asChild size="sm">
            <Link href="/check">Check a depot</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}

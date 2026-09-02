import Link from "next/link";
import { LayoutDashboard } from "lucide-react";

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
              {/* The name is the way back into the signed-in area -- a farmer
                  who lands here again should not have to hunt for it. */}
              <Link
                href="/dashboard"
                className="bg-secondary text-foreground hover:bg-accent focus-visible:ring-ring inline-flex max-w-[10rem] items-center gap-1.5 truncate rounded-md px-2.5 py-1.5 text-sm font-medium focus-visible:ring-2 focus-visible:outline-none"
              >
                <LayoutDashboard className="size-4 shrink-0" aria-hidden />
                <span className="truncate">{farmerName}</span>
                <span className="sr-only">— open my dashboard</span>
              </Link>
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

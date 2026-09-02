import Link from "next/link";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

/**
 * Console chrome. Deliberately scoped to the (console) group so the sign-in
 * page does not render a nav bar and a sign-out button.
 */
export default function ConsoleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-full flex-col">
      <header className="border-border border-b">
        <div className="mx-auto flex w-full max-w-5xl items-center gap-4 px-4 py-3">
          <Logo />
          <Link
            href="/depot"
            className="font-heading text-muted-foreground hover:text-foreground hidden text-sm tracking-wide sm:block"
          >
            GATE CONSOLE
          </Link>
          <Separator orientation="vertical" className="bg-border h-5" />
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/depot" className="hover:underline">
              Verify arrival
            </Link>
            <Link href="/depot/farmers" className="hover:underline">
              All farmers
            </Link>
          </nav>
          <form action="/api/depot/sign-out" method="post" className="ml-auto">
            <Button type="submit" variant="ghost" size="sm">
              Sign out
            </Button>
          </form>
        </div>
      </header>
      {children}
    </div>
  );
}

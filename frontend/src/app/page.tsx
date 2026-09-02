import { CircleCheck, CircleSlash } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

// Placeholder. Renders both verdict states so the token set is visibly
// wired up. The wizard and the rules engine are not built yet.
export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-10">
      <header className="flex flex-col gap-1">
        <h1 className="text-3xl">Kilimo Hakika</h1>
        <p className="text-muted-foreground">
          Know whether the depot will serve you — before you travel.
        </p>
      </header>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            {/* Icon + text label, never colour alone */}
            <CircleCheck className="text-proceed size-5" aria-hidden />
            <CardTitle className="text-proceed">Proceed</CardTitle>
          </div>
          <CardDescription>
            Your documents satisfy the requirements for this depot.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex items-baseline justify-between">
            <span className="text-sm">Allocation cap</span>
            {/* Body-size statutory number: --statutory-strong, not --statutory */}
            <span className="text-statutory-strong font-heading text-lg">
              4 bags &middot; 2 acres
            </span>
          </div>
          <Separator className="bg-border/40" />
          <div className="flex items-baseline justify-between">
            <span className="text-sm">Official total</span>
            {/* Large enough for brass at 3:1 */}
            <span className="text-statutory font-heading text-2xl">
              10,000 KES
            </span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <CircleSlash className="text-gate size-5" aria-hidden />
            <CardTitle className="text-gate">Do not travel</CardTitle>
          </div>
          <CardDescription>You are missing required documents.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Badge variant="outline">Original National ID</Badge>
          <Badge variant="outline">E-Voucher SMS code</Badge>
        </CardContent>
      </Card>

      <Button className="self-start" disabled>
        Start check — not built yet
      </Button>
    </main>
  );
}

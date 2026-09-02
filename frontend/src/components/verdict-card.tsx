import { CircleCheck, CircleSlash, FileText } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { TriageResult } from "@/lib/triage/types";

const kes = (amount: number) => `${amount.toLocaleString("en-KE")} KES`;

/**
 * The answer screen. Renders all three questions at once: the verdict, the
 * gap list, and the statutory cost.
 *
 * Colour never carries the verdict alone — every state pairs its colour with
 * an icon and a text label, because this decides whether someone spends bus
 * fare and a red/green pair is the worst case for colour-blind readers.
 */
export function VerdictCard({ result }: { result: TriageResult }) {
  const proceed = result.verdict === "PROCEED";
  const Icon = proceed ? CircleCheck : CircleSlash;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Icon
              className={`size-6 ${proceed ? "text-proceed" : "text-gate"}`}
              aria-hidden
            />
            <CardTitle
              className={`text-2xl ${proceed ? "text-proceed" : "text-gate"}`}
            >
              {proceed ? "Proceed" : "Do not travel"}
            </CardTitle>
          </div>
          <CardDescription>
            {proceed
              ? `Your documents meet the requirements for ${result.depot.name}.`
              : `${result.depot.name} will turn you away. You are missing ${result.missing.length} required ${result.missing.length === 1 ? "item" : "items"}.`}
          </CardDescription>
        </CardHeader>

        {!proceed && (
          <CardContent>
            <h3 className="mb-3 text-sm">What you are missing</h3>
            <ul className="flex flex-col gap-3">
              {result.missing.map((item) => (
                <li key={item.id} className="flex flex-col gap-1">
                  <span className="text-gate font-medium">{item.label}</span>
                  <span className="text-muted-foreground text-sm">
                    {item.detail}
                  </span>
                  {item.satisfiedByAnyOf && (
                    <span className="text-muted-foreground text-sm">
                      Any one of:{" "}
                      {item.satisfiedByAnyOf.map((o) => o.label).join(" or ")}
                    </span>
                  )}
                  <span className="text-muted-foreground text-xs">
                    {item.source}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        )}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Official allocation and cost</CardTitle>
          <CardDescription>
            Gazetted rates for {result.depot.program}. Do not pay more than
            this.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Row label="Your land" value={`${result.acres} acres`} />
          <Row
            label="Allocation cap"
            value={`${result.costing.bags} × ${result.costing.unit}`}
            statutory
          />
          {result.costing.cappedByDepotCeiling && (
            <p className="text-muted-foreground text-sm">
              Your acreage entitles you to more, but {result.depot.name} caps
              each farmer at {result.costing.maxBags} bags.
            </p>
          )}
          <Row
            label="Price per bag"
            value={kes(result.costing.pricePerBagKes)}
            statutory
          />
          <Separator className="bg-border/40" />
          <div className="flex items-baseline justify-between">
            <span className="text-sm">Official total</span>
            {/* Large size, so gazette brass clears 3:1 on ledger paper */}
            <span className="text-statutory font-heading text-3xl">
              {kes(result.costing.totalKes)}
            </span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileText className="text-muted-foreground size-4" aria-hidden />
            <CardTitle className="text-base">Where this comes from</CardTitle>
          </div>
          <CardDescription>
            Every rule above is taken from these sources. Rules version{" "}
            {result.rulesVersion}.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="text-muted-foreground flex flex-col gap-1 text-sm">
            {result.citations.map((citation) => (
              <li key={citation}>{citation}</li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

function Row({
  label,
  value,
  statutory,
}: {
  label: string;
  value: string;
  statutory?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <span className="text-sm">{label}</span>
      {/* Body-size statutory numbers use --statutory-strong: gazette brass is
          3.0:1 on ledger paper and fails AA below large text. */}
      <span
        className={
          statutory
            ? "text-statutory-strong font-heading text-lg"
            : "font-heading text-lg"
        }
      >
        {value}
      </span>
    </div>
  );
}

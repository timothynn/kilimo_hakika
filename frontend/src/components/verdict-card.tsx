import { Banknote, CircleCheck, CircleSlash, FileText, MapPin } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { ApiTriageResponse } from "@/lib/depot-api";

const kes = (amount: number) => `${amount.toLocaleString("en-KE")} KES`;

/**
 * The answer screen. Renders all three questions at once: the verdict, the
 * gap list, and the statutory cost.
 *
 * Colour never carries the verdict alone — every state pairs its colour with
 * an icon and a text label, because this decides whether someone spends bus
 * fare and a red/green pair is the worst case for colour-blind readers.
 *
 * The verdict shown here is produced entirely by the FastAPI engine. Nothing
 * on this screen is computed in the browser.
 */
export function VerdictCard({ result }: { result: ApiTriageResponse }) {
  const proceed = result.verdict.will_be_served;
  const Icon = proceed ? CircleCheck : CircleSlash;

  const { financial_breakdown: money, gap_analysis: gaps } = result;
  const missingCount = gaps.missing_documents.length;

  return (
    <div className="flex flex-col gap-4">
      <Card className="pt-0">
        {/* Filled block, not coloured text. The surfaces are green now, so
            green text would read as decoration; a solid band reads as a
            stamp. Colour still never carries it alone -- icon and words
            both say which verdict this is. */}
        <div
          className={`flex items-center gap-3 px-6 py-5 ${
            proceed
              ? "bg-proceed text-proceed-foreground"
              : "bg-gate text-gate-foreground"
          }`}
        >
          <Icon className="size-7 shrink-0" aria-hidden />
          <span className="font-heading text-3xl tracking-wide uppercase">
            {proceed ? "Proceed" : "Do not travel"}
          </span>
        </div>

        <CardHeader>
          <CardDescription>{result.verdict.summary}</CardDescription>
        </CardHeader>

        <CardContent className="flex flex-col gap-6">
          {/* ---------------------------------------------------------------
              THE CASH RULE.
              Shown on PROCEED as prominently as on DO NOT TRAVEL, and placed
              above the gap list on a green verdict. A farmer just told to
              travel is precisely the one about to leave the house, and cash
              at the counter is refused outright — a perfect set of documents
              still ends in a wasted trip without a way to pay.
              --------------------------------------------------------------- */}
          {!result.payment_notice.cash_accepted_at_depot && (
            <div className="border-gate/40 bg-gate/5 flex flex-col gap-2 rounded-md border-2 p-4">
              <div className="text-gate flex items-center gap-2">
                <Banknote className="size-5 shrink-0" aria-hidden />
                <h3 className="font-heading text-base tracking-wide uppercase">
                  {result.payment_notice.headline}
                </h3>
              </div>
              <p className="text-sm">{result.payment_notice.notice}</p>
              <ul className="text-muted-foreground ml-1 list-inside list-disc text-sm">
                {result.payment_notice.accepted_means.map((means) => (
                  <li key={means}>{means}</li>
                ))}
              </ul>
              <p className="text-muted-foreground text-xs">
                {result.payment_notice.authority}
              </p>
            </div>
          )}

          {/* Question 2: what am I lacking? */}
          {missingCount > 0 && (
            <section>
              <h3 className="mb-3 text-sm">
                What you are missing ({missingCount})
              </h3>
              <ul className="flex flex-col gap-3">
                {result.document_checklist
                  .filter((item) => item.required && !item.held)
                  .map((item) => (
                    <li key={item.code} className="flex items-start gap-3">
                      <FileText
                        className="text-gate mt-0.5 size-4 shrink-0"
                        aria-hidden
                      />
                      <span className="flex flex-col">
                        <span className="font-medium">{item.label}</span>
                        <span className="text-muted-foreground text-xs">
                          {item.authority}
                        </span>
                      </span>
                    </li>
                  ))}
              </ul>
            </section>
          )}

          {/* Anything blocking the trip that is not simply a missing document:
              a photocopy presented instead of an original, an expired voucher,
              a closed depot, a depot outside the catchment. */}
          {gaps.rejection_reasons.length > 0 && (
            <section>
              <h3 className="mb-3 text-sm">Why you would be turned away</h3>
              <ol className="flex flex-col gap-2">
                {gaps.rejection_reasons.map((reason) => (
                  <li key={reason} className="text-sm leading-relaxed">
                    {reason}
                  </li>
                ))}
              </ol>
            </section>
          )}

          <Separator />

          {/* Question 3: what is the official cost? Shown even on a
              DO NOT TRAVEL — a farmer who does not know the gazetted price
              cannot tell they are being overcharged on the next trip. */}
          <section className="grid gap-4 sm:grid-cols-2">
            <Figure
              label="Your allocation"
              value={`${money.allocated_bags} × 50kg bag${money.allocated_bags === 1 ? "" : "s"}`}
              statutory
              note={`${result.allocation_basis.planting_bags_per_acre} planting + ${result.allocation_basis.top_dressing_bags_per_acre} top-dressing per acre, ceiling ${result.allocation_basis.max_bags_per_farmer} bags.`}
            />
            <Figure
              label="Official price"
              value={`${kes(money.price_per_bag)} per bag`}
              statutory
              note="Gazetted subsidised price."
            />
          </section>

          <div className="flex flex-col gap-1">
            <span className="text-muted-foreground text-sm">
              Official total
            </span>
            <span className="text-statutory font-heading text-3xl">
              {kes(money.total_cost_kes)}
            </span>
            <span className="text-muted-foreground text-xs">
              {result.allocation_basis.explanation}
            </span>
          </div>

          {result.next_steps.length > 0 && (
            <>
              <Separator />
              <section>
                <h3 className="mb-3 text-sm">What to do next</h3>
                <ol className="flex list-inside list-decimal flex-col gap-2 text-sm">
                  {result.next_steps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
              </section>
            </>
          )}

          {/* Only ever gazetted Government depots. Never a vendor listing. */}
          {result.alternative_depots.length > 0 && (
            <>
              <Separator />
              <section>
                <h3 className="mb-3 text-sm">
                  Government depots currently serving your county
                </h3>
                <ul className="flex flex-col gap-2">
                  {result.alternative_depots.slice(0, 4).map((depot) => (
                    <li key={depot.depot_id} className="flex items-start gap-2 text-sm">
                      <MapPin
                        className="text-muted-foreground mt-0.5 size-4 shrink-0"
                        aria-hidden
                      />
                      <span>
                        <span className="font-medium">{depot.name}</span>
                        <span className="text-muted-foreground">
                          {" "}
                          — {depot.town}, {depot.operating_hours}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Where this comes from</CardTitle>
          <CardDescription>
            Every rule above is taken from these sources. Your holding was
            matched to {result.resolved_location.ward} Ward,{" "}
            {result.resolved_location.constituency} Constituency,{" "}
            {result.resolved_location.county} County.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="text-muted-foreground flex list-inside list-disc flex-col gap-1 text-sm">
            <li>{result.policy_grounding.circular}</li>
            <li>{result.policy_grounding.operating_procedure}</li>
            <li>Depot status: {result.policy_grounding.depot_status}</li>
          </ul>
          <p className="text-muted-foreground mt-4 text-xs">
            {money.statutory_notice}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function Figure({
  label,
  value,
  note,
  statutory,
}: {
  label: string;
  value: string;
  note?: string;
  statutory?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-muted-foreground text-sm">{label}</span>
      {/* Body-size statutory numbers use --statutory-strong: gazette brass
          fails AA below 18.66px bold. */}
      <span
        className={
          statutory
            ? "text-statutory-strong font-heading text-lg"
            : "font-medium"
        }
      >
        {value}
      </span>
      {note && <span className="text-muted-foreground text-xs">{note}</span>}
    </div>
  );
}

import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  Ban,
  CircleCheck,
  CircleSlash,
  ClipboardList,
  Coins,
  FileWarning,
  Landmark,
  ReceiptText,
  ShieldCheck,
  Wallet,
} from "lucide-react";

import { Logo } from "@/components/logo";
import { Reveal } from "@/components/reveal";
import { SiteHeader } from "@/components/site-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { currentFarmer } from "@/lib/session";
import { loadRules } from "@/lib/triage/rules";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function LandingPage() {
  const rules = loadRules();
  const farmer = await currentFarmer();
  const depotCount = rules.depots.length;

  return (
    <div className="flex min-h-full flex-col">
      <SiteHeader farmerName={farmer?.fullName} />

      {/* ---------------------------------------------------------------- Hero */}
      <section className="relative overflow-hidden">
        <div className="mx-auto grid w-full max-w-6xl items-center gap-10 px-4 py-14 lg:grid-cols-2 lg:py-20">
          <Reveal className="flex flex-col gap-6">
            <Badge
              variant="outline"
              className="text-muted-foreground w-fit gap-2 py-1"
            >
              <Landmark className="size-3.5" aria-hidden />
              {depotCount} government depots · rules version {rules.version}
            </Badge>

            <h1 className="text-4xl leading-[1.05] sm:text-5xl lg:text-6xl">
              Know if the depot
              <br />
              will serve you.
              <br />
              <span className="text-proceed">Before you travel.</span>
            </h1>

            <p className="text-muted-foreground max-w-lg text-lg">
              Farmers lose a day&apos;s wages and a full fare getting turned
              away at the gate over one missing stamp. Answer three questions
              and find out first — free, and without an account.
            </p>

            <div className="flex flex-wrap items-center gap-3">
              <Button asChild size="lg" className="h-13 px-7 text-base">
                <Link href="/check">
                  Check a depot now <ArrowRight />
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="h-13 px-7 text-base"
              >
                <Link href="/signup">Create an account</Link>
              </Button>
            </div>

            <p className="text-muted-foreground text-sm">
              No payments. No middlemen. Just the official rules.
            </p>
          </Reveal>

          <Reveal delay={120} className="relative">
            <div className="relative aspect-4/3 overflow-hidden rounded-2xl">
              <Image
                src="/img/farmers-smallholder.jpg"
                alt="Smallholder farmers working a field in Kenya"
                fill
                priority
                sizes="(max-width: 1024px) 100vw, 50vw"
                className="object-cover"
              />
            </div>

            {/* Floating proof of what the answer actually looks like. */}
            <div className="bg-card border-border absolute -bottom-6 -left-4 w-64 rounded-xl border p-4 shadow-lg sm:left-6">
              <div className="flex items-center gap-2">
                <CircleCheck className="text-proceed size-5" aria-hidden />
                <span className="font-heading text-proceed text-lg tracking-wide">
                  PROCEED
                </span>
              </div>
              <Separator className="bg-border my-3" />
              <div className="flex items-baseline justify-between text-sm">
                <span className="text-muted-foreground">2 acres</span>
                <span className="font-heading text-statutory-strong">
                  4 bags
                </span>
              </div>
              <div className="mt-1 flex items-baseline justify-between">
                <span className="text-muted-foreground text-sm">
                  Official total
                </span>
                <span className="font-heading text-statutory text-2xl">
                  10,000 KES
                </span>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ------------------------------------------------------------- Problem */}
      <section id="problem" className="bg-card border-border border-y">
        <div className="mx-auto w-full max-w-6xl px-4 py-16 lg:py-24">
          <Reveal className="max-w-2xl">
            <h2 className="text-3xl sm:text-4xl">
              The gate is where the money disappears
            </h2>
            <p className="text-muted-foreground mt-4 text-lg">
              Depots are centralised. Getting to one costs real money and a
              whole day. Nothing tells a farmer in advance whether the trip is
              worth making.
            </p>
          </Reveal>

          <div className="mt-12 grid gap-6 lg:grid-cols-3">
            {[
              {
                icon: Wallet,
                title: "Fare spent for nothing",
                body: "A round trip to a centralised depot costs a day of work plus transport. Turned away at the gate, none of it comes back.",
              },
              {
                icon: FileWarning,
                title: "One missing stamp",
                body: "A lease without the area chief's stamp. An e-voucher SMS on a phone left at home. Requirements nobody printed anywhere the farmer could read.",
              },
              {
                icon: Coins,
                title: "Prices nobody can check",
                body: "Farmers who do not know the gazetted cap or price have no way to tell when an official is overcharging them.",
              },
            ].map((item, index) => (
              <Reveal key={item.title} delay={index * 100}>
                <Card className="h-full">
                  <CardContent className="flex h-full flex-col gap-3 pt-6">
                    <item.icon className="text-gate size-7" aria-hidden />
                    <h3 className="text-xl">{item.title}</h3>
                    <p className="text-muted-foreground text-sm">{item.body}</p>
                  </CardContent>
                </Card>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------- Three answers */}
      <section id="answers">
        <div className="mx-auto w-full max-w-6xl px-4 py-16 lg:py-24">
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal className="order-2 lg:order-1">
              <div className="relative aspect-3/4 overflow-hidden rounded-2xl">
                <Image
                  src="/img/maize-field.jpg"
                  alt="Maize growing on a smallholding in Kenya"
                  fill
                  sizes="(max-width: 1024px) 100vw, 50vw"
                  className="object-cover"
                />
              </div>
            </Reveal>

            <div className="order-1 flex flex-col gap-8 lg:order-2">
              <Reveal>
                <h2 className="text-3xl sm:text-4xl">
                  Three questions, answered before you leave home
                </h2>
              </Reveal>

              {[
                {
                  n: "01",
                  icon: BadgeCheck,
                  title: "Will I be served?",
                  body: "A straight yes or no. PROCEED, or DO NOT TRAVEL. No maybes, no percentages.",
                },
                {
                  n: "02",
                  icon: ClipboardList,
                  title: "What am I lacking?",
                  body: "If no, an itemised list of exactly which physical documents are missing — each one citing the circular that requires it.",
                },
                {
                  n: "03",
                  icon: ReceiptText,
                  title: "What is the official cost?",
                  body: "Your allocation from your acreage, and the total at gazetted rates. Shown even when the answer is no, so you know the real price next time.",
                },
              ].map((item, index) => (
                <Reveal key={item.n} delay={index * 100}>
                  <div className="flex gap-4">
                    <span className="font-heading text-statutory text-2xl">
                      {item.n}
                    </span>
                    <div className="flex flex-col gap-1">
                      <h3 className="flex items-center gap-2 text-xl">
                        <item.icon
                          className="text-proceed size-5"
                          aria-hidden
                        />
                        {item.title}
                      </h3>
                      <p className="text-muted-foreground text-sm">
                        {item.body}
                      </p>
                    </div>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------------- How it works */}
      <section id="how" className="bg-card border-border border-y">
        <div className="mx-auto w-full max-w-6xl px-4 py-16 lg:py-24">
          <Reveal className="max-w-2xl">
            <h2 className="text-3xl sm:text-4xl">Three steps, about a minute</h2>
          </Reveal>

          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {[
              {
                step: "1",
                title: "Your land",
                body: "How many acres you farm. That sets your allocation.",
              },
              {
                step: "2",
                title: "Your depot",
                body: "Which depot you plan to travel to. Requirements differ between them.",
              },
              {
                step: "3",
                title: "Your documents",
                body: "Tick only what you have with you right now. The gaps are the answer.",
              },
            ].map((item, index) => (
              <Reveal key={item.step} delay={index * 120}>
                <div className="flex flex-col gap-3">
                  <span className="bg-proceed text-proceed-foreground font-heading flex size-11 items-center justify-center rounded-full text-xl">
                    {item.step}
                  </span>
                  <h3 className="text-xl">{item.title}</h3>
                  <p className="text-muted-foreground text-sm">{item.body}</p>
                </div>
              </Reveal>
            ))}
          </div>

          <Reveal delay={200} className="mt-12">
            <Button asChild size="lg" className="h-13 px-7 text-base">
              <Link href="/check">
                Start a check <ArrowRight />
              </Link>
            </Button>
          </Reveal>
        </div>
      </section>

      {/* --------------------------------------------------------- Two platforms */}
      <section>
        <div className="mx-auto w-full max-w-6xl px-4 py-16 lg:py-24">
          <Reveal className="max-w-2xl">
            <h2 className="text-3xl sm:text-4xl">Two doors in</h2>
            <p className="text-muted-foreground mt-4 text-lg">
              One for farmers checking before they travel. One for depot
              officers verifying who turns up at the gate.
            </p>
          </Reveal>

          <div className="mt-12 grid gap-6 lg:grid-cols-2">
            <Reveal>
              <Card className="h-full pt-0">
                <div className="relative h-44 w-full">
                  <Image
                    src="/img/kenya-corn.jpg"
                    alt="Harvested maize cobs"
                    fill
                    sizes="(max-width: 1024px) 100vw, 50vw"
                    className="object-cover"
                  />
                </div>
                <CardContent className="flex flex-col gap-4">
                  <h3 className="text-2xl">I am a farmer</h3>
                  <p className="text-muted-foreground text-sm">
                    Check any depot for free without signing up. Create an
                    account only if you want the depot officer to find your
                    details at the gate — it is never required to get an
                    answer.
                  </p>
                  <div className="mt-auto flex flex-wrap gap-2">
                    <Button asChild>
                      <Link href="/check">Check a depot</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/login">Farmer sign in</Link>
                    </Button>
                    <Button asChild variant="ghost">
                      <Link href="/signup">Sign up</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </Reveal>

            <Reveal delay={120}>
              <Card className="h-full pt-0">
                <div className="relative h-44 w-full">
                  <Image
                    src="/img/farming-kenya.jpg"
                    alt="Farmland in Kenya"
                    fill
                    sizes="(max-width: 1024px) 100vw, 50vw"
                    className="object-cover"
                  />
                </div>
                <CardContent className="flex flex-col gap-4">
                  <h3 className="text-2xl">I am a depot officer</h3>
                  <p className="text-muted-foreground text-sm">
                    Look a farmer up by ID at the gate, see the verdict they
                    were given before travelling, and record what they actually
                    collected. Access is restricted.
                  </p>
                  <div className="mt-auto flex flex-wrap gap-2">
                    <Button asChild>
                      <Link href="/depot/sign-in">Gate console sign-in</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------ What we are not */}
      <section className="bg-primary text-primary-foreground">
        <div className="mx-auto w-full max-w-6xl px-4 py-16 lg:py-20">
          <Reveal className="max-w-2xl">
            <h2 className="text-3xl sm:text-4xl">What this is not</h2>
            <p className="mt-4 text-lg opacity-80">
              The value here is being trustworthy about official rules. Every
              other feature would dilute that, so there are none.
            </p>
          </Reveal>

          <div className="mt-10 grid gap-6 sm:grid-cols-3">
            {[
              {
                icon: Ban,
                title: "No farming advice",
                body: "Zero crop, planting or yield recommendations.",
              },
              {
                icon: ShieldCheck,
                title: "No payments",
                body: "No M-Pesa, no transactions. We show the statutory price; we never take money.",
              },
              {
                icon: CircleSlash,
                title: "No marketplace",
                body: "No vendors, no listings, no comparison shopping.",
              },
            ].map((item, index) => (
              <Reveal key={item.title} delay={index * 100}>
                <div className="flex flex-col gap-2">
                  <item.icon className="size-6 opacity-80" aria-hidden />
                  <h3 className="text-lg">{item.title}</h3>
                  <p className="text-sm opacity-70">{item.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ Footer */}
      <footer className="border-border border-t">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-10">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <Logo />
            <Link href="/check" className="text-sm underline">
              Check a depot
            </Link>
            <Link href="/login" className="text-sm underline">
              Farmer sign in
            </Link>
            <Link href="/depot/sign-in" className="text-sm underline">
              Depot officer
            </Link>
          </div>

          <p className="text-muted-foreground max-w-3xl text-sm">
            Requirements and prices are read from official circulars, currently{" "}
            {rules.version}. Each rule on a result screen cites its source so
            you can check it yourself. If a circular changes and this tool has
            not caught up, the circular is right and we are wrong.
          </p>

          {/* CC BY and CC BY-SA images require credit wherever they appear.
              See CREDITS.md — do not remove this without removing the photos. */}
          <p className="text-muted-foreground text-xs">
            Photographs: “Women smallholder farmers in Kenya” by McKay Savage
            (CC BY 2.0); “Maize farming in Kenya” by Kuza Kilimo and “Farming
            in Kenya” by Shirleen.Kay (CC BY-SA 4.0); “Kenya corn” by USAID
            Africa Bureau (public domain). Via Wikimedia Commons.
          </p>
        </div>
      </footer>
    </div>
  );
}

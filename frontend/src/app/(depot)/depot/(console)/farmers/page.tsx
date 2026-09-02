import Link from "next/link";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { listFarmers } from "@/lib/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function AllFarmersPage({
  searchParams,
}: {
  searchParams: Promise<{ county?: string }>;
}) {
  const { county } = await searchParams;
  const farmers = listFarmers({ county });
  const counties = [...new Set(listFarmers().map((f) => f.county))].sort();

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl">All registered farmers</h1>
        <p className="text-muted-foreground text-sm">
          {farmers.length} {farmers.length === 1 ? "farmer" : "farmers"}
          {county ? ` in ${county}` : ""}
        </p>
      </header>

      {counties.length > 1 && (
        <nav className="flex flex-wrap items-center gap-3 text-sm">
          <Link
            href="/depot/farmers"
            className={county ? "underline" : "font-medium"}
          >
            All counties
          </Link>
          {counties.map((name) => (
            <Link
              key={name}
              href={`/depot/farmers?county=${encodeURIComponent(name)}`}
              className={county === name ? "font-medium" : "underline"}
            >
              {name}
            </Link>
          ))}
        </nav>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Registry</CardTitle>
          <CardDescription>
            Personal details. Only look up a farmer who is in front of you.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {farmers.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No farmers registered yet. Farmers can register themselves from
              the public check page.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>ID</TableHead>
                  <TableHead>County</TableHead>
                  <TableHead className="text-right">Acres</TableHead>
                  <TableHead>Phone</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {farmers.map((farmer) => (
                  <TableRow key={farmer.id}>
                    <TableCell>
                      <Link
                        href={`/depot/farmers/${farmer.id}`}
                        className="underline"
                      >
                        {farmer.fullName}
                      </Link>
                    </TableCell>
                    {/* Only the last four digits exist in the database. */}
                    <TableCell className="text-muted-foreground">
                      &hellip;{farmer.nationalIdLast4}
                    </TableCell>
                    <TableCell>{farmer.county}</TableCell>
                    <TableCell className="text-right">{farmer.acres}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {farmer.phone}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </main>
  );
}

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; next?: string }>;
}) {
  const { error, next } = await searchParams;

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-4 py-16">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl">Depot officer sign-in</h1>
        <p className="text-muted-foreground text-sm">
          Kilimo Hakika gate console
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Enter the depot passphrase</CardTitle>
          <CardDescription>
            Shared passphrase, issued by the programme administrator.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            action="/api/depot/sign-in"
            method="post"
            className="flex flex-col gap-4"
          >
            <input type="hidden" name="next" value={next ?? "/depot"} />
            <div className="flex flex-col gap-2">
              <Label htmlFor="passphrase">Passphrase</Label>
              <Input
                id="passphrase"
                name="passphrase"
                type="password"
                autoComplete="current-password"
                className="h-12"
                required
              />
            </div>

            {/* Deliberately vague: never say whether the passphrase exists,
                only that this attempt failed. */}
            {error && <p className="text-gate text-sm">Incorrect passphrase.</p>}

            <Button type="submit">Sign in</Button>
          </form>
        </CardContent>
      </Card>

      <p className="text-muted-foreground text-xs">
        This console shows farmer personal details. Do not sign in on a shared
        or public device.
      </p>
    </main>
  );
}

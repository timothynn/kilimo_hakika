import { AppShell } from "@/components/app-shell";
import { currentFarmer } from "@/lib/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Side menu for the farmer's signed-in area: /dashboard and /check/*. The
 * group is a URL-invisible route group, so adding a page here gives it the
 * menu without changing its path. The landing page and the auth screens sit
 * outside it and keep their own chrome.
 *
 * A signed-out visitor gets the same shell on /check -- that page is usable
 * without an account and must stay that way. The menu just drops the entries
 * that need one.
 */
export default async function FarmerAppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const farmer = await currentFarmer();

  return (
    <AppShell
      variant="farmer"
      farmerName={farmer?.fullName}
      title="MY DASHBOARD"
    >
      {children}
    </AppShell>
  );
}

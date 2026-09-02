import { AppShell } from "@/components/app-shell";

/**
 * Console chrome. Deliberately scoped to the (console) group so the sign-in
 * page does not render a side menu and a sign-out button.
 */
export default function ConsoleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AppShell variant="depot" title="GATE CONSOLE">
      {children}
    </AppShell>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ClipboardCheck,
  History,
  Home,
  IdCard,
  LayoutDashboard,
  LogIn,
  LogOut,
  UserRound,
  Users,
  type LucideIcon,
} from "lucide-react";

import { Logo } from "@/components/logo";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";

type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Match this href exactly. Use on a parent that has child routes. */
  exact?: boolean;
};

const FARMER_NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/check", label: "Check a depot", icon: ClipboardCheck, exact: true },
  { href: "/check/history", label: "My past checks", icon: History },
  { href: "/check/profile", label: "My details", icon: UserRound },
  { href: "/", label: "Home", icon: Home, exact: true },
];

/** Farmer entries that mean nothing without an account. */
const FARMER_ACCOUNT_ONLY = new Set([
  "/dashboard",
  "/check/history",
  "/check/profile",
]);

const DEPOT_NAV: NavItem[] = [
  { href: "/depot", label: "Verify arrival", icon: IdCard, exact: true },
  { href: "/depot/farmers", label: "All farmers", icon: Users },
];

function isActive(pathname: string, item: NavItem): boolean {
  return item.exact ? pathname === item.href : pathname.startsWith(item.href);
}

/**
 * Side menu shell for the two signed-in surfaces: the farmer's area
 * (/dashboard and /check/*) and the depot gate console.
 *
 * The menu is a nav, not a gate. `/check` stays reachable without an account,
 * so the farmer variant renders for a signed-out visitor too -- it just swaps
 * the footer for a sign-in link and drops the entries in
 * FARMER_ACCOUNT_ONLY, which need an account to mean anything.
 */
export function AppShell({
  variant,
  farmerName,
  title,
  children,
}: {
  variant: "farmer" | "depot";
  /** Farmer variant only. Absent means signed out. */
  farmerName?: string;
  /** Shown beside the trigger on small screens, where the page h1 scrolls away. */
  title: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const farmer = variant === "farmer";

  const items = farmer
    ? FARMER_NAV.filter(
        (item) => farmerName || !FARMER_ACCOUNT_ONLY.has(item.href)
      )
    : DEPOT_NAV;

  return (
    <TooltipProvider>
      <SidebarProvider>
        <Sidebar collapsible="icon">
          <SidebarHeader className="px-3 py-4 group-data-[collapsible=icon]:px-1.5">
            <Logo className="group-data-[collapsible=icon]:[&>span:last-child]:hidden" />
          </SidebarHeader>

          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel>
                {farmer ? "Farmer" : "Gate console"}
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {items.map((item) => (
                    <SidebarMenuItem key={item.href}>
                      <SidebarMenuButton
                        asChild
                        isActive={isActive(pathname, item)}
                        tooltip={item.label}
                      >
                        <Link href={item.href}>
                          <item.icon />
                          <span>{item.label}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>

          <SidebarSeparator />

          <SidebarFooter>
            <SidebarMenu>
              {farmer && !farmerName ? (
                <SidebarMenuItem>
                  <SidebarMenuButton asChild tooltip="Sign in">
                    <Link href="/login">
                      <LogIn />
                      <span>Sign in</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ) : (
                <>
                  {farmerName && (
                    <div className="text-muted-foreground truncate px-2 pb-1 text-xs group-data-[collapsible=icon]:hidden">
                      Signed in as {farmerName}
                    </div>
                  )}
                  <SidebarMenuItem>
                    {/*
                      Plain form post, not a fetch: sign-out has to work on a
                      gate terminal with a dead connection to the JS bundle.
                    */}
                    <form
                      action={
                        farmer ? "/api/farmer/sign-out" : "/api/depot/sign-out"
                      }
                      method="post"
                    >
                      <SidebarMenuButton
                        type="submit"
                        className="w-full"
                        tooltip="Sign out"
                      >
                        <LogOut />
                        <span>Sign out</span>
                      </SidebarMenuButton>
                    </form>
                  </SidebarMenuItem>
                </>
              )}
            </SidebarMenu>
          </SidebarFooter>

          <SidebarRail />
        </Sidebar>

        <SidebarInset>
          <header className="border-border bg-background/80 sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b px-4 backdrop-blur-md">
            <SidebarTrigger className="-ml-1" />
            <span className="font-heading text-muted-foreground text-sm tracking-wide">
              {title}
            </span>
          </header>
          {children}
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  );
}

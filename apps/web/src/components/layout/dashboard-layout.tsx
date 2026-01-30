"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import {
  Languages,
  FileText,
  History,
  Book,
  Settings,
  LogOut,
  Menu,
  Moon,
  Sun,
  User,
} from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { useAuth, Features, useHasHydrated } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  feature?: string;
}

const navItems: NavItem[] = [
  { label: "Translate", href: "/translate", icon: Languages, feature: Features.TRANSLATE_TEXT },
  { label: "Files", href: "/files", icon: FileText, feature: Features.UPLOAD_FILES },
  { label: "History", href: "/history", icon: History, feature: Features.VIEW_HISTORY },
  { label: "Glossary", href: "/glossary", icon: Book, feature: Features.USE_GLOSSARY },
  { label: "Admin", href: "/admin", icon: Settings, feature: Features.ADMIN_PANEL },
];

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const { user, isAuthenticated, isLoading, logout, hasFeature, checkAuth } = useAuth();
  const hasHydrated = useHasHydrated();

  useEffect(() => {
    if (hasHydrated) {
      checkAuth();
    }
  }, [checkAuth, hasHydrated]);

  useEffect(() => {
    if (hasHydrated && !isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, router, hasHydrated]);

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  // Safe feature check with hydration guard
  const safeHasFeature = (feature: string): boolean => {
    if (!hasHydrated || !user || !user.features || !Array.isArray(user.features)) {
      return false;
    }
    return hasFeature(feature);
  };

  const visibleNavItems = navItems.filter(
    (item) => !item.feature || safeHasFeature(item.feature)
  );

  // Show loading while not hydrated or still loading auth
  if (!hasHydrated || isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="spinner h-8 w-8" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  // Safe user initials calculation
  const getUserInitials = (): string => {
    if (user?.display_name && user.display_name.trim().length > 0) {
      const parts = user.display_name.trim().split(" ").filter(Boolean);
      if (parts.length > 0) {
        return parts.map((n) => n[0] || "").join("").toUpperCase().slice(0, 2) || "U";
      }
    }
    if (user?.username && user.username.length > 0) {
      return user.username.slice(0, 2).toUpperCase();
    }
    return "U";
  };

  const userInitials = getUserInitials();

  return (
    <div className="flex min-h-screen flex-col">
      {/* Dev Mode Banner */}
      {process.env.NEXT_PUBLIC_DEV_MODE === "true" && (
        <div className="dev-mode-banner">
          DEV MODE - Using Mock Services
        </div>
      )}

      {/* Header */}
      <header className={cn(
        "sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60",
        process.env.NEXT_PUBLIC_DEV_MODE === "true" && "top-10"
      )}>
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-6">
            {/* Logo */}
            <Link href="/translate" className="flex items-center gap-2">
              <Languages className="h-6 w-6 text-primary" />
              <span className="text-xl font-bold">TRJM</span>
            </Link>

            {/* Navigation */}
            <nav className="hidden md:flex items-center gap-1">
              {visibleNavItems.map((item) => {
                const Icon = item.icon;
                const isActive = pathname === item.href;
                return (
                  <Link key={item.href} href={item.href}>
                    <Button
                      variant={isActive ? "secondary" : "ghost"}
                      size="sm"
                      className="gap-2"
                    >
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </Button>
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            {/* Theme Toggle */}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            >
              <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
              <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
              <span className="sr-only">Toggle theme</span>
            </Button>

            {/* User Menu */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="gap-2">
                  <Avatar className="h-8 w-8">
                    <AvatarFallback>{userInitials}</AvatarFallback>
                  </Avatar>
                  <span className="hidden sm:inline-block">
                    {user?.display_name || user?.username}
                  </span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>
                  <div className="flex flex-col space-y-1">
                    <p className="text-sm font-medium">{user?.display_name || user?.username}</p>
                    <p className="text-xs text-muted-foreground">{user?.email}</p>
                    <p className="text-xs text-muted-foreground">Role: {user?.role?.name}</p>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout} className="text-destructive">
                  <LogOut className="mr-2 h-4 w-4" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            {/* Mobile Menu */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild className="md:hidden">
                <Button variant="ghost" size="icon">
                  <Menu className="h-5 w-5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                {visibleNavItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <DropdownMenuItem key={item.href} asChild>
                      <Link href={item.href} className="flex items-center gap-2">
                        <Icon className="h-4 w-4" />
                        {item.label}
                      </Link>
                    </DropdownMenuItem>
                  );
                })}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1">
        <div className="container py-6">{children}</div>
      </main>

      {/* Footer */}
      <footer className="border-t py-4">
        <div className="container flex items-center justify-between text-sm text-muted-foreground">
          <p>TRJM Agentic AI Translator</p>
          <p>v1.0.0</p>
        </div>
      </footer>
    </div>
  );
}

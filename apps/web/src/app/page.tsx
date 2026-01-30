"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, isLoading, checkAuth } = useAuth();

  useEffect(() => {
    checkAuth().then(() => {
      // After checking auth, redirect appropriately
    });
  }, [checkAuth]);

  useEffect(() => {
    if (!isLoading) {
      if (isAuthenticated) {
        router.replace("/translate");
      } else {
        router.replace("/login");
      }
    }
  }, [isAuthenticated, isLoading, router]);

  return (
    <div className="flex h-screen items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="spinner h-8 w-8" />
        <p className="text-muted-foreground">Loading...</p>
      </div>
    </div>
  );
}

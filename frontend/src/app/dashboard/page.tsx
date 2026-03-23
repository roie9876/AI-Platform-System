"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function DashboardPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/dashboard/agents");
  }, [router]);

  return (
    <div className="flex items-center justify-center h-full">
      <p className="text-gray-500">Redirecting...</p>
    </div>
  );
}

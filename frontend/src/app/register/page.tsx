"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function RegisterPage() {
  const router = useRouter();

  useEffect(() => {
    router.push("/login");
  }, [router]);

  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <div className="max-w-md w-full rounded-lg border border-gray-200 bg-white p-8 shadow-sm dark:border-gray-800 dark:bg-gray-950">
        <h1 className="text-2xl font-bold tracking-tight mb-4">Registration</h1>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
          Registration is managed by your organization&apos;s administrator.
          Please sign in with your Microsoft account.
        </p>
        <Link
          href="/login"
          className="block w-full rounded-md bg-gray-900 px-4 py-2 text-center text-sm font-medium text-white hover:bg-gray-800 dark:bg-gray-50 dark:text-gray-900 dark:hover:bg-gray-200"
        >
          Go to Sign In
        </Link>
      </div>
    </main>
  );
}

import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="max-w-md w-full rounded-lg border border-gray-200 bg-white p-8 shadow-sm dark:border-gray-800 dark:bg-gray-950">
        <h1 className="text-3xl font-bold tracking-tight mb-2">
          AI Agent Platform
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mb-6">
          Multi-tenant AI Agent Platform as a Service. Create, configure, and
          orchestrate AI agents through a self-service interface.
        </p>
        <Link
          href="/login"
          className="inline-flex items-center justify-center rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 dark:bg-gray-50 dark:text-gray-900 dark:hover:bg-gray-200"
        >
          Get Started
        </Link>
      </div>
    </main>
  );
}

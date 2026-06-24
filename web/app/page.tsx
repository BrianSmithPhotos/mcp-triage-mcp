import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 items-center justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex flex-1 w-full max-w-2xl flex-col items-center justify-center gap-10 py-32 px-8">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Planner Triage
        </h1>
        <div className="flex flex-col gap-4 w-full sm:flex-row sm:justify-center">
          <Link
            href="/triage"
            className="flex h-12 items-center justify-center rounded-full bg-foreground px-6 text-background transition-colors hover:bg-[#383838] dark:hover:bg-[#ccc]"
          >
            Triage &quot;Message Center Posts&quot;
          </Link>
          <Link
            href="/chat"
            className="flex h-12 items-center justify-center rounded-full border border-solid border-black/[.08] px-6 transition-colors hover:bg-black/[.04] dark:border-white/[.145] dark:hover:bg-[#1a1a1a]"
          >
            Ad-hoc Planner chat
          </Link>
        </div>
      </main>
    </div>
  );
}

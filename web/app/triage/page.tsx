"use client";

import { useState } from "react";
import Link from "next/link";
import { applyTriageDecisions, fetchTriagePreview, TriageDecision, TriagePreview } from "@/lib/api";

export default function TriagePage() {
  const [preview, setPreview] = useState<TriagePreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [applied, setApplied] = useState<string[] | null>(null);

  async function runPreview() {
    setLoading(true);
    setError(null);
    setApplied(null);
    try {
      setPreview(await fetchTriagePreview());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function apply() {
    if (!preview) return;
    setApplying(true);
    setError(null);
    try {
      const moves = preview.decisions.filter(
        (d): d is TriageDecision => !!d.target_bucket_id
      );
      const result = await applyTriageDecisions(moves);
      setApplied(result.applied);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="flex flex-col flex-1 items-center bg-zinc-50 font-sans dark:bg-black px-8 py-16">
      <div className="flex w-full max-w-3xl flex-col gap-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Triage Preview</h1>
          <Link href="/" className="text-sm underline">
            Back
          </Link>
        </div>

        <button
          onClick={runPreview}
          disabled={loading}
          className="h-11 rounded-full bg-foreground px-6 text-background disabled:opacity-50"
        >
          {loading ? "Fetching..." : "Run Triage Preview"}
        </button>

        {error && <p className="text-red-600">{error}</p>}

        {preview && (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Plan: <strong>{preview.plan}</strong> — Source bucket:{" "}
              <strong>{preview.todo_bucket}</strong> — {preview.decisions.length} task(s)
            </p>

            {preview.decisions.length === 0 ? (
              <p>No tasks in the To Do bucket.</p>
            ) : (
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b">
                    <th className="py-2">Task</th>
                    <th className="py-2">Move to</th>
                    <th className="py-2">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.decisions.map((d) => (
                    <tr key={d.task_id} className="border-b border-zinc-200 dark:border-zinc-800">
                      <td className="py-2 pr-4">{d.title}</td>
                      <td className="py-2 pr-4 font-medium">
                        {d.target_bucket_name}
                        {!d.target_bucket_id && (
                          <span className="ml-2 text-red-600">(bucket not found)</span>
                        )}
                      </td>
                      <td className="py-2 text-zinc-600 dark:text-zinc-400">{d.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {preview.decisions.length > 0 && (
              <button
                onClick={apply}
                disabled={applying}
                className="h-11 self-start rounded-full border border-solid border-black/[.2] px-6 disabled:opacity-50"
              >
                {applying ? "Applying..." : "Apply moves"}
              </button>
            )}

            {applied && (
              <p className="text-green-700 dark:text-green-400">
                Moved {applied.length} task(s).
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

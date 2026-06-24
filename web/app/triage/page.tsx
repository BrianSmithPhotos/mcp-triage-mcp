"use client";

import { useState } from "react";
import Link from "next/link";
import {
  applyTriageDecisions,
  deleteBucketTasks,
  fetchDeletedBucketPreview,
  fetchTriagePreview,
  DeletedBucketPreview,
  TriageDecision,
  TriagePreview,
} from "@/lib/api";

export default function TriagePage() {
  const [preview, setPreview] = useState<TriagePreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [applied, setApplied] = useState<string[] | null>(null);

  const [deletePreview, setDeletePreview] = useState<DeletedBucketPreview | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleted, setDeleted] = useState<string[] | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

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

  async function runDeletePreview() {
    setDeleteLoading(true);
    setDeleteError(null);
    setDeleted(null);
    setConfirmDelete(false);
    try {
      setDeletePreview(await fetchDeletedBucketPreview());
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeleteLoading(false);
    }
  }

  async function confirmAndDelete() {
    if (!deletePreview) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      const result = await deleteBucketTasks(deletePreview.tasks);
      setDeleted(result.deleted);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeleting(false);
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

        <hr className="border-zinc-200 dark:border-zinc-800" />

        <div className="flex flex-col gap-4">
          <h2 className="text-xl font-semibold">Clear &quot;To Be Deleted&quot;</h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Permanently deletes every task currently in the fallback bucket. This cannot be
            undone. The bucket itself is kept for future triage runs.
          </p>

          <button
            onClick={runDeletePreview}
            disabled={deleteLoading}
            className="h-11 self-start rounded-full bg-foreground px-6 text-background disabled:opacity-50"
          >
            {deleteLoading ? "Fetching..." : "Preview tasks to delete"}
          </button>

          {deleteError && <p className="text-red-600">{deleteError}</p>}

          {deletePreview && (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Bucket: <strong>{deletePreview.bucket}</strong> —{" "}
                {deletePreview.tasks.length} task(s) will be permanently deleted
              </p>

              {deletePreview.tasks.length > 0 && (
                <ul className="list-disc pl-5 text-sm">
                  {deletePreview.tasks.map((t) => (
                    <li key={t.task_id}>{t.title}</li>
                  ))}
                </ul>
              )}

              {deletePreview.tasks.length > 0 && (
                <>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={confirmDelete}
                      onChange={(e) => setConfirmDelete(e.target.checked)}
                    />
                    I understand this permanently deletes {deletePreview.tasks.length} task(s)
                  </label>

                  <button
                    onClick={confirmAndDelete}
                    disabled={!confirmDelete || deleting}
                    className="h-11 self-start rounded-full bg-red-600 px-6 text-white disabled:opacity-50"
                  >
                    {deleting ? "Deleting..." : "Delete permanently"}
                  </button>
                </>
              )}

              {deleted && (
                <p className="text-green-700 dark:text-green-400">
                  Deleted {deleted.length} task(s).
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

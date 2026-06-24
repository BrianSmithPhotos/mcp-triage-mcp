const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8001";

export type TriageDecision = {
  task_id: string;
  title: string;
  etag: string;
  target_bucket_name: string;
  target_bucket_id: string | null;
  reason: string;
};

export type TriagePreview = {
  plan: string;
  todo_bucket: string;
  decisions: TriageDecision[];
};

export async function fetchTriagePreview(): Promise<TriagePreview> {
  const res = await fetch(`${BACKEND_URL}/triage/preview`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function applyTriageDecisions(decisions: TriageDecision[]) {
  const res = await fetch(`${BACKEND_URL}/triage/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decisions }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export type DeletableTask = {
  task_id: string;
  title: string;
  etag: string;
};

export type DeletedBucketPreview = {
  plan: string;
  bucket: string;
  tasks: DeletableTask[];
};

export async function fetchDeletedBucketPreview(): Promise<DeletedBucketPreview> {
  const res = await fetch(`${BACKEND_URL}/triage/deleted-preview`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteBucketTasks(tasks: DeletableTask[]) {
  const res = await fetch(`${BACKEND_URL}/triage/delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tasks }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export type ChatMessage = {
  role: "system" | "user" | "assistant" | "tool";
  content?: string | null;
  tool_calls?: unknown[];
  tool_call_id?: string;
};

export async function sendChat(messages: ChatMessage[]): Promise<{ messages: ChatMessage[] }> {
  const res = await fetch(`${BACKEND_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

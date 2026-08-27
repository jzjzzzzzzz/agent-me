export type Source = { title: string; path: string; excerpt: string; score: number };
export type ChatResponse = { answer: string; mode: string; sources: Source[] };
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
export async function ask(question: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/api/v1/chat`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question})});
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json() as Promise<ChatResponse>;
}

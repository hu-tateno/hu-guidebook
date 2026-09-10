const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface DocumentOut {
  id: number;
  admission_year: number;
  title: string;
  page_count: number;
}

export interface ChunkOut {
  chunk_id: number;
  document_id: number;
  page_number: number;
  text: string;
  bbox: [number, number, number, number];
  score: number;
  matched_terms: string[];
}

export interface StageTraceOut {
  stage: number;
  label: string;
  query_terms: string[];
  result_count: number;
}

export interface SearchResponse {
  search_query_id: number;
  admission_year: number;
  document_id: number;
  query: string;
  stages: StageTraceOut[];
  results: ChunkOut[];
  answer: string | null;
}

export interface PopularHighlightOut {
  chunk_id: number;
  page_number: number;
  text: string;
  count: number;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`${response.status} ${response.statusText}: ${detail}`);
  }
  return response.json() as Promise<T>;
}

export function listDocuments(): Promise<DocumentOut[]> {
  return apiFetch<DocumentOut[]>("/api/documents");
}

export function documentFileUrl(documentId: number): string {
  return `${API_BASE}/api/documents/${documentId}/file`;
}

export function search(params: {
  admissionYear: number;
  documentId?: number;
  query: string;
  deviceId: string;
  wantAnswer?: boolean;
}): Promise<SearchResponse> {
  return apiFetch<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify({
      admission_year: params.admissionYear,
      document_id: params.documentId,
      query: params.query,
      device_id: params.deviceId,
      want_answer: params.wantAnswer ?? true,
    }),
  });
}

export function recordHighlight(params: { chunkId: number; deviceId: string }): Promise<void> {
  return apiFetch<{ status: string }>("/api/highlights", {
    method: "POST",
    body: JSON.stringify({ chunk_id: params.chunkId, device_id: params.deviceId }),
  }).then(() => undefined);
}

export function popularHighlights(params: {
  admissionYear: number;
  documentId?: number;
  limit?: number;
}): Promise<PopularHighlightOut[]> {
  const search = new URLSearchParams({ admission_year: String(params.admissionYear) });
  if (params.documentId != null) search.set("document_id", String(params.documentId));
  if (params.limit != null) search.set("limit", String(params.limit));
  return apiFetch<PopularHighlightOut[]>(`/api/highlights/popular?${search.toString()}`);
}

export function submitEvaluation(params: {
  searchQueryId: number;
  suggestionHelpful?: boolean;
  answerResolved?: boolean;
  category?: string;
  comment?: string;
  deviceId: string;
}): Promise<void> {
  return apiFetch<{ status: string }>("/api/evaluations", {
    method: "POST",
    body: JSON.stringify({
      search_query_id: params.searchQueryId,
      suggestion_helpful: params.suggestionHelpful,
      answer_resolved: params.answerResolved,
      category: params.category,
      comment: params.comment,
      device_id: params.deviceId,
    }),
  }).then(() => undefined);
}

// --- admin ---

export function adminLogin(password: string): Promise<void> {
  return apiFetch<{ status: string }>("/api/admin/login", {
    method: "POST",
    body: JSON.stringify({ password }),
  }).then(() => undefined);
}

export function adminLogout(): Promise<void> {
  return apiFetch<{ status: string }>("/api/admin/logout", { method: "POST" }).then(() => undefined);
}

export interface EvaluationStats {
  total_searches: number;
  total_evaluations: number;
  helpful_rate: number | null;
  resolved_rate: number | null;
}

export function adminMetrics(params: { admissionYear?: number; category?: string }): Promise<EvaluationStats> {
  const search = new URLSearchParams();
  if (params.admissionYear != null) search.set("admission_year", String(params.admissionYear));
  if (params.category) search.set("category", params.category);
  const qs = search.toString();
  return apiFetch<EvaluationStats>(`/api/admin/metrics${qs ? `?${qs}` : ""}`);
}

export interface LowRatedQuestion {
  evaluation_id: number;
  admission_year: number;
  category: string | null;
  suggestion_helpful: boolean | null;
  answer_resolved: boolean | null;
  comment: string | null;
  created_at: string | null;
  query_text: string;
}

export function adminLowRatedQuestions(params: { admissionYear?: number; limit?: number }): Promise<LowRatedQuestion[]> {
  const search = new URLSearchParams();
  if (params.admissionYear != null) search.set("admission_year", String(params.admissionYear));
  if (params.limit != null) search.set("limit", String(params.limit));
  const qs = search.toString();
  return apiFetch<LowRatedQuestion[]>(`/api/admin/low-rated-questions${qs ? `?${qs}` : ""}`);
}

export function adminExportCsvUrl(admissionYear?: number): string {
  const search = new URLSearchParams();
  if (admissionYear != null) search.set("admission_year", String(admissionYear));
  const qs = search.toString();
  return `${API_BASE}/api/admin/export.csv${qs ? `?${qs}` : ""}`;
}

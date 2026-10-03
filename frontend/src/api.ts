export type RunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface Run {
  id: string;
  document_id: string;
  status: RunStatus;
  current_step: string | null;
  error: string | null;
  summary: Record<string, any>;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  steps?: string[];
}

export interface Doc {
  id: string;
  filename: string;
  size: number;
  format: string | null;
  page_count: number | null;
  created_at: string;
  latest_run: Run | null;
  duplicate?: boolean;
}

export interface RunEvent {
  id: number;
  run_id: string;
  ts: string;
  type: "step_started" | "step_finished" | "progress" | "decision" | "warning" | "error" | "run_finished";
  step: string | null;
  message: string;
  data: Record<string, any>;
}

export interface Decision {
  id: number;
  step: string;
  subject: string;
  choice: string;
  rule_id: string | null;
  inputs: Record<string, any>;
  alternatives: { choice: string; reason_rejected: string }[];
  confidence: number | null;
  reasoning: string;
  ts: string;
}

export interface Chunk {
  id: string;
  seq: number;
  text: string;
  tokens: number;
  pages: number[];
  bboxes: { page: number; bbox: number[] }[];
  section: string | null;
  element_types: string[];
  strategy_id: string;
}

export interface SearchHit {
  rank: number;
  chunk_id: string;
  seq: number;
  text: string;
  tokens: number;
  pages: number[];
  bboxes: { page: number; bbox: number[] }[];
  section: string | null;
  element_types: string[];
  scores: {
    dense: number | null;
    dense_rank: number | null;
    lexical: number | null;
    lexical_rank: number | null;
    fused: number | null;
    rerank: number | null;
  };
}

export type SearchMode = "hybrid" | "dense" | "lexical";

export interface SearchResult {
  run_id: string | null;
  mode: SearchMode;
  model?: string;
  collection?: string;
  reranker?: string;
  candidates?: number;
  notes: string[];
  timings_ms: Record<string, number>;
  hits: SearchHit[];
}

export interface EmbeddingPoint {
  chunk_id: string;
  x: number;
  y: number;
  seq: number;
  pages: number[];
  section: string | null;
  element_types: string[];
  tokens: number;
  preview: string;
  norm: number;
}

export interface Projection {
  collection: string;
  dim?: number;
  count: number;
  explained_variance?: number[];
  norm?: { min: number; mean: number; max: number };
  points: EmbeddingPoint[];
  note?: string;
}

export interface Neighbor {
  chunk_id: string;
  score: number;
  pages: number[];
  section: string | null;
  element_types: string[];
  preview: string;
}


export interface PageProfile {
  page: number;
  label: string;
  rule_id: string;
  confidence: number;
  parser: string | null;
  features: {
    text_chars: number;
    text_area_ratio: number;
    images: number;
    image_area_ratio: number;
    drawings: number;
    tables: number;
    table_area_ratio: number;
    table_text_share?: number;
    size_hist: Record<string, number>;
    evidence: {
      conditions: Record<string, { threshold: number; actual: number }>;
      evaluated: { rule: string; matched: boolean }[];
    };
  };
}

export interface Element {
  id: number;
  page: number;
  seq: number;
  type: "text" | "title" | "table" | "figure";
  bbox: [number, number, number, number];
  content: string;
  source_tool: string;
  meta: {
    figure_type?: string;
    caption?: string;
    region_source?: string;
    area_ratio?: number;
    vlm_seconds?: number;
    empty_cell_ratio?: number;
    reextracted?: boolean;
  } | null;
}

export type StorageKey = "data_dir" | "db_url" | "qdrant_url";

export interface StorageItem {
  key: StorageKey;
  label: string;
  effective: string;
  configured: string;
  source: "env" | "dotenv" | "file" | "default";
  locked: boolean;
  pending: boolean;
}

export interface StorageState {
  settings_file: string;
  items: StorageItem[];
  database: string;
  vector_store: string;
  usage: { key: string; label: string; path: string; bytes: number | null }[];
  restart_required: boolean;
  key_required: boolean;
  editable_here: boolean;
  active_runs: number;
}

export const pageImage =(docId: string, page: number, dpi = 96) => `/api/documents/${docId}/pages/${page}.png?dpi=${dpi}`;

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  documents: () => fetch("/api/documents").then(json<Doc[]>),
  upload: (files: File[]) => {
    const body = new FormData();
    for (const file of files) body.append("files", file);
    return fetch("/api/documents/batch", { method: "POST", body }).then(json<Doc[]>);
  },
  startRun: (docId: string) => fetch(`/api/documents/${docId}/runs`, { method: "POST" }).then(json<Run>),
  startRuns: (docIds: string[]) =>
    fetch("/api/documents/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_ids: docIds }),
    }).then(json<Run[]>),
  storage: () => fetch("/api/settings/storage").then(json<StorageState>),
  updateStorage: (changes: Partial<Record<StorageKey, string>>, apiKey?: string) =>
    fetch("/api/settings/storage", {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}) },
      body: JSON.stringify(changes),
    }).then(json<StorageState>),
  run: (runId: string) => fetch(`/api/runs/${runId}`).then(json<Run>),
  cancelRun: (runId: string) => fetch(`/api/runs/${runId}/cancel`, { method: "POST" }).then(json<{ cancelled: boolean }>),
  pages: (runId: string) => fetch(`/api/runs/${runId}/pages`).then(json<PageProfile[]>),
  elements: (runId: string, page: number) => fetch(`/api/runs/${runId}/elements?page=${page}`).then(json<Element[]>),
  decisions: (runId: string, subject: string) =>
    fetch(`/api/runs/${runId}/decisions?subject=${encodeURIComponent(subject)}`).then(json<Decision[]>),
  search: (body: {
    query: string;
    run_id?: string;
    document_id?: string;
    top_k?: number;
    mode?: SearchMode;
    rerank?: boolean;
    dense_weight?: number;
    lexical_weight?: number;
  }) =>
    fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(json<SearchResult>),
  capabilities: () => fetch("/api/search/capabilities").then(json<{ embedding_model: string; reranker: string | null }>),
  chunks: (runId: string, params: { offset?: number; limit?: number; page?: number; type?: string; q?: string } = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]));
    return fetch(`/api/runs/${runId}/chunks?${qs}`).then(json<{ total: number; items: Chunk[] }>);
  },
  embeddings: (runId: string) => fetch(`/api/runs/${runId}/embeddings`).then(json<Projection>),
  neighbors: (runId: string, chunkId: string, k = 5) => fetch(`/api/runs/${runId}/chunks/${chunkId}/neighbors?k=${k}`).then(json<Neighbor[]>),
};

/** Subscribe to a run's event stream. Reconnects from the last seen id; stops after run_finished. */
export function streamRun(runId: string, onEvent: (e: RunEvent) => void): () => void {
  let last = 0;
  let closed = false;
  let es: EventSource | null = null;
  let retry: number | undefined;

  const open = () => {
    es = new EventSource(`/api/runs/${runId}/stream?after=${last}`);
    es.addEventListener("run_event", (msg) => {
      const ev: RunEvent = JSON.parse((msg as MessageEvent).data);
      last = ev.id;
      onEvent(ev);
      if (ev.type === "run_finished") stop();
    });
    es.onerror = () => {
      es?.close();
      if (!closed) retry = window.setTimeout(open, 2000);
    };
  };
  const stop = () => {
    closed = true;
    window.clearTimeout(retry);
    es?.close();
  };
  open();
  return stop;
}

export interface User {
  id: string;
  name: string;
  email: string;
  library_id: string;
}
export interface Media {
  source: MediaSource;
  original_filename: string;
  id: string;
  title: string;
  note: string;
  tags: string[];
  favorite: boolean;
  status: "PROCESSING" | "READY" | "FAILED";
  duration_ms: number;
  width: number;
  height: number;
  size_bytes: number;
  created_at: string;
  updated_at: string;
  storage_mode: string;
  assets: Record<string, string>;
  cell_count: number;
  shelf_ids: string[];
  collection_ids: string[];
}
export interface MediaSource {
  provider: "local_upload" | "youtube" | "x" | "instagram" | "tiktok";
  label: string;
  url: string | null;
  external_id: string | null;
  author: string;
  start_ms: number;
  thumbnail_url: string | null;
  capabilities: {
    embed: boolean;
    download: boolean;
    analyze: boolean;
    cells: boolean;
  };
}
export interface ImportResult {
  media: Media;
  created: boolean;
  start_ms: number;
  metadata_available: boolean;
}
export interface Cell {
  shelf_ids: string[];
  storage_mode: string;
  collection_ids: string[];
  id: string;
  media_id: string;
  title: string;
  note: string;
  tags: string[];
  start_ms: number;
  end_ms: number;
  origin: string;
  analysis_run_id: string | null;
  media_title: string;
  thumbnail?: string;
  created_at: string;
}
export interface HeaderFrame {
  x: number;
  y: number;
  zoom: number;
}
export interface Group {
  id: string;
  name: string;
  description: string;
  color: string;
  header_url?: string | null;
  header_frame?: HeaderFrame;
  media_count: number;
  cell_count: number;
}
export interface Job {
  id: string;
  media_id: string;
  media_title: string;
  batch_id: string | null;
  kind: string;
  state: string;
  progress: number;
  attempt: number;
  error_message: string | null;
}
export interface Page<T> {
  items: T[];
  total: number;
}
export interface Stats {
  managed_count: number;
  reference_count: number;
  limits: {
    managed: number;
    references: number;
    cells: number;
    cells_per_media: number;
    clip_ms: number;
    analysis_runs: number;
  };
  media_count: number;
  cell_count: number;
  collection_count: number;
  shelf_count: number;
  duration_ms: number;
  size_bytes: number;
  stored_bytes: number;
}
export interface Event {
  event_type?: string;
  id: string;
  media_id?: string;
  analysis_run_id: string;
  start_ms: number;
  end_ms: number;
  label: string;
  confidence: number | null;
}
export interface Transcript {
  id: string;
  media_id?: string;
  start_ms: number;
  end_ms: number;
  text: string;
  media_title?: string;
}
export interface Analysis {
  runs: {
    id: string;
    analyzer: string;
    status: string;
    model_version: string;
    created_at: string;
  }[];
  events: Event[];
  transcripts: Transcript[];
  has_more: boolean;
}
export interface Capability {
  id: string;
  name: string;
  description: string;
  available: boolean;
}
export interface SearchResults {
  media: Media[];
  cells: Cell[];
  transcripts: Transcript[];
  events: (Event & { media_title: string })[];
  total: number;
  counts: Record<string, number>;
}

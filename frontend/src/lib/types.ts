export type TournamentMode =
  | "FFA"
  | "FFA KO"
  | "2vs2"
  | "2v2 GP"
  | "3vs3"
  | "4vs4"
  | "5vs5"
  | "6vs6"
  | "Limit Breaker";

export interface TournamentOptions {
  "32track": boolean;
  "200cc": boolean;
  ott: boolean;
}

export interface WorkflowProcessRequest {
  event_id: string;
  mode: TournamentMode;
  players: PlayerEntry[];
  options: TournamentOptions;
  event_date: string;
}

export interface PlayerEntry {
  name: string;
  score: number | "";
  mii_data: string;
  seed?: number | "" | null;
  round_scores?: Array<number | "" | null>;
}

export interface TournamentResult {
  name: string;
  ranking: number;
  score: number;
  old_mmr: number;
  new_mmr: number;
  mmr_change: number;
  is_rated: boolean;
  boosted: boolean;
  bonus: number;
  mii_data: string;
  seed?: number | null;
  round_scores?: Array<number | null>;
  rounds_played?: number;
  total_score?: number;
}

export interface TournamentResponse {
  event_id: string;
  mode: TournamentMode;
  processed_at: string;
  results: TournamentResult[];
  options: TournamentOptions;
  event_date: string;
}

export interface SessionUser {
  id: string;
  display_name: string;
  avatar_url?: string | null;
  authorized: boolean;
}

export interface SessionState {
  authenticated: boolean;
  user: SessionUser | null;
}

export interface SavedImageRequest {
  event_id: string;
  subtitle?: string;
  title?: string;
  persist?: boolean;
}

export interface SheetsUpdateResult {
  name: string;
  score: number;
  new_mmr: number;
  mmr_change: number;
  is_rated: boolean;
  bonus: number;
}

export interface SheetsUpdateRequest {
  event_id: string;
  results: SheetsUpdateResult[];
  tournament?: TournamentResponse;
  persist_image?: boolean;
  subtitle?: string;
  title?: string;
}

export interface SheetsUpdateResponse {
  success: boolean;
  updated_cells: number;
  timestamp: string;
  message: string;
}

export interface NextEventIdResponse {
  event_id: string;
  season?: number | null;
}

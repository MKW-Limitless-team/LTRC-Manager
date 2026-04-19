import type {
  SavedImageRequest,
  SessionState,
  SheetsUpdateRequest,
  SheetsUpdateResponse,
  TournamentResponse,
  WorkflowProcessRequest
} from "./types";

const APP_BASE_PATH = import.meta.env.VITE_APP_BASE_PATH ?? "";

function normaliseBaseUrl(value: string): string {
  if (!value) {
    return "";
  }
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

function resolveApiBaseUrl(): string {
  const configured = normaliseBaseUrl(import.meta.env.VITE_API_BASE_URL ?? "");
  if (configured) {
    return configured;
  }

  if (import.meta.env.DEV) {
    const { hostname, protocol } = window.location;
    return `${protocol}//${hostname}:8000`;
  }

  return "";
}

const API_BASE_URL = resolveApiBaseUrl();

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.message ?? payload?.detail ?? "Request failed";
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function getLoginUrl(): string {
  return `${API_BASE_URL}/auth/login`;
}

export function getSessionState(): Promise<SessionState> {
  return apiFetch<SessionState>("/auth/me");
}

export function getNextEventId(): Promise<{ event_id: string; season: number }> {
  return apiFetch<{ event_id: string; season: number }>("/ltrc/next-event-id");
}

export function getPlayerNames(): Promise<{ players: string[] }> {
  return apiFetch<{ players: string[] }>("/ltrc/players");
}

export function logout(): Promise<{ success: boolean }> {
  return apiFetch<{ success: boolean }>("/auth/logout", { method: "POST" });
}

export function processWorkflow(data: WorkflowProcessRequest): Promise<TournamentResponse> {
  return apiFetch<TournamentResponse>("/ltrc/process", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function saveTournamentResults(data: TournamentResponse): Promise<TournamentResponse> {
  return apiFetch<TournamentResponse>("/ltrc/results/save", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function updateSheets(data: SheetsUpdateRequest): Promise<SheetsUpdateResponse> {
  return apiFetch<SheetsUpdateResponse>("/ltrc/update", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export async function generateImage(data: SavedImageRequest): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/ltrc/images/generate`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(data)
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.message ?? payload?.detail ?? "Image generation failed";
    throw new Error(message);
  }

  return response.blob();
}

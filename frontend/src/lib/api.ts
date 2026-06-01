const BASE = "/api";

async function req<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Erro desconhecido");
  }
  return res.json();
}

// --- Auth ---
export const getMe = () => req<User>("/auth/me");

// --- Characters ---
export const getCharacters = () => req<Character[]>("/characters");
export const createCharacter = (body: { name: string; cls?: string }) =>
  req<Character>("/characters", { method: "POST", body: JSON.stringify(body) });
export const updateCharacter = (id: number, body: { name?: string; cls?: string }) =>
  req<Character>(`/characters/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteCharacter = (id: number) =>
  req<{ ok: boolean }>(`/characters/${id}`, { method: "DELETE" });

// --- Schedules ---
export const getSchedules = () => req<Schedule[]>("/schedules");
export const getFreeSlots = () => req<Slot[]>("/schedules/free-slots");
export const createSchedule = (body: ScheduleIn) =>
  req<Schedule>("/schedules", { method: "POST", body: JSON.stringify(body) });
export const reschedule = (id: number, new_start: string) =>
  req<Schedule>(`/schedules/${id}/reschedule`, { method: "PATCH", body: JSON.stringify({ new_start }) });
export const cancelSchedule = (id: number) =>
  req<{ ok: boolean }>(`/schedules/${id}`, { method: "DELETE" });

// --- Pokémon ---
export const getPokemon = () => req<Pokemon[]>("/pokemon");
export const getMyPokemon = () => req<Pokemon[]>("/pokemon/my");
export const assignPokemon = (id: number) =>
  req<Pokemon>(`/pokemon/${id}/assign`, { method: "PATCH" });
export const unassignPokemon = (id: number) =>
  req<Pokemon>(`/pokemon/${id}/unassign`, { method: "PATCH" });

// --- History (admin) ---
export const getHistory = (params?: { entity_type?: string; limit?: number; offset?: number }) => {
  const qs = new URLSearchParams();
  if (params?.entity_type) qs.set("entity_type", params.entity_type);
  if (params?.limit)       qs.set("limit", String(params.limit));
  if (params?.offset)      qs.set("offset", String(params.offset));
  return req<HistoryEntry[]>(`/history?${qs}`);
};

// --- Types ---
export interface User {
  discord_id: string;
  username: string;
  avatar_url: string | null;
  is_admin: boolean;
}

export interface Character {
  id: number;
  name: string;
  class: string | null;
}

export interface Schedule {
  id: number;
  party_id: number;
  difficulty: "HARD" | "NW";
  start_time: string;
  end_time: string;
  status: "pending" | "confirmed" | "rescheduled" | "missed" | "cancelled";
}

export interface Slot {
  start: string;
  end: string;
}

export interface ScheduleIn {
  character_id: number;
  role: string;
  difficulty: string;
  start_time: string;
  party_members: { discord_id: string; role: string }[];
}

export interface Pokemon {
  id: number;
  name: string;
  image_url: string | null;
  category: "A" | "B" | "C";
  assigned_to: string | null;
  assigned_at: string | null;
}

export interface HistoryEntry {
  id: number;
  actor_id: string | null;
  entity_type: string;
  entity_id: number | null;
  action: string;
  detail: string | null;
  happened_at: string;
}

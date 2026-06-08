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
export const updateMySettings = (notify_lead_minutes: number) =>
  req<User>("/auth/me", { method: "PATCH", body: JSON.stringify({ notify_lead_minutes }) });

// --- Characters ---
export const getCharacters = () => req<Character[]>("/characters");
export const createCharacter = (body: { name: string }) =>
  req<Character>("/characters", { method: "POST", body: JSON.stringify(body) });
export const updateCharacter = (id: number, body: { name?: string }) =>
  req<Character>(`/characters/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteCharacter = (id: number) =>
  req<{ ok: boolean }>(`/characters/${id}`, { method: "DELETE" });

// --- Members ---
export const getMembers = () => req<Member[]>("/members");

// --- Schedules ---
export const getSchedules = () => req<Schedule[]>("/schedules");
export const getFreeSlots = (exclude?: number) =>
  req<Slot[]>(`/schedules/free-slots${exclude != null ? `?exclude=${exclude}` : ""}`);
export const getCalendar  = () => req<CalendarParty[]>("/schedules/calendar");
export const createSchedule = (body: ScheduleIn) =>
  req<Schedule>("/schedules", { method: "POST", body: JSON.stringify(body) });
export const reschedule = (id: number, new_start: string, scope: "once" | "all" = "once", force = false) =>
  req<Schedule>(`/schedules/${id}/reschedule`, { method: "PATCH", body: JSON.stringify({ new_start, scope, force }) });
export const addMember = (id: number, body: { discord_id: string; role: string; character_id: number | null }) =>
  req<{ ok: boolean }>(`/schedules/${id}/add-member`, { method: "POST", body: JSON.stringify(body) });
export const cancelSchedule = (id: number) =>
  req<{ ok: boolean }>(`/schedules/${id}`, { method: "DELETE" });
export const confirmPresence = (id: number) =>
  req<{ ok: boolean }>(`/schedules/${id}/confirm`, { method: "POST" });
export const leaveParty = (id: number) =>
  req<{ ok: boolean; cancelled: boolean }>(`/schedules/${id}/leave`, { method: "POST" });
export const setMyCharacter = (id: number, character_id: number) =>
  req<{ ok: boolean }>(`/schedules/${id}/my-character`, { method: "PATCH", body: JSON.stringify({ character_id }) });
export const promoteColeader = (id: number, user_id: string, coleader: boolean) =>
  req<{ ok: boolean }>(`/schedules/${id}/promote`, { method: "POST", body: JSON.stringify({ user_id, coleader }) });
export const kickMember = (id: number, user_id: string) =>
  req<{ ok: boolean }>(`/schedules/${id}/kick`, { method: "POST", body: JSON.stringify({ user_id }) });

// --- Pokémon ---
export const getPokemon = () => req<Pokemon[]>("/pokemon");
export const getMyPokemon = () => req<Pokemon[]>("/pokemon/my");
export const createPokemon = (body: { name: string; image_url?: string; category: string }) =>
  req<Pokemon>("/pokemon", { method: "POST", body: JSON.stringify(body) });
export const updatePokemon = (id: number, body: { name?: string; image_url?: string; category?: string }) =>
  req<Pokemon>(`/pokemon/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deletePokemon = (id: number) =>
  req<{ ok: boolean }>(`/pokemon/${id}`, { method: "DELETE" });
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
  notify_lead_minutes?: number;
}

export interface Character {
  id: number;
  name: string;
}

export interface Member {
  discord_id: string;
  username: string;
  avatar_url: string | null;
  characters: Character[];
}

export interface Schedule {
  id: number;
  party_id: number;
  difficulty: "HARD" | "NW";
  start_time: string;
  end_time: string;
  weekday: number;  // 0=Seg .. 6=Dom — slot FIXO recorrente
  hour: number;
  is_override?: boolean;          // remarcada só esta semana
  override_start?: string | null; // ocorrência efetiva desta semana (quando is_override)
  organizer_id: string | null;
  status: "pending" | "confirmed" | "rescheduled" | "missed" | "cancelled";
  members: ScheduleMember[];
  is_member: boolean;
  is_leader?: boolean;
  can_manage?: boolean;
}

export interface ScheduleMember {
  discord_id: string;
  nick: string;
  role: "DPS" | "SUP" | "TANK";
  character: string | null;
  confirmed?: boolean;
  is_coleader?: boolean;
}

export interface CalendarParty {
  schedule_id: number;
  weekday: number;
  hour: number;
  difficulty: "HARD" | "NW";
  is_override?: boolean;
  members: ScheduleMember[];
}

// 0=Seg..6=Dom (Python weekday) para exibição
export const WEEKDAY_LABEL = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];

// Composição da PT: 1 tank, 2 dps, 1 suporte
export type Role = "TANK" | "DPS" | "SUP";
export const ROLE_CAPACITY: Record<Role, number> = { TANK: 1, DPS: 2, SUP: 1 };

export interface Slot {
  start: string;
  end: string;
  free: boolean;
}

export interface ScheduleIn {
  character_id: number | null;
  role: string | null;
  difficulty: string;
  start_time: string;
  party_members: { discord_id: string; role: string; character_id: number | null }[];
  include_self: boolean;
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
  actor_name: string;
  entity_type: string;
  entity_id: number | null;
  action: string;
  detail: string | null;
  summary: string;
  happened_at: string;
}

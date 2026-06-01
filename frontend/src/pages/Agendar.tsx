import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getCharacters, getFreeSlots, createSchedule } from "../lib/api";
import { useAuth } from "../lib/useAuth";

const ROLES = ["DPS", "SUP", "TANK"] as const;
const DIFFICULTIES = ["HARD", "NW"] as const;

interface PartyMemberInput { discord_id: string; role: string }

export default function Agendar() {
  const { user } = useAuth();
  const navigate  = useNavigate();
  const qc        = useQueryClient();

  const { data: characters = [] } = useQuery({ queryKey: ["characters"], queryFn: getCharacters });
  const { data: slots      = [] } = useQuery({ queryKey: ["free-slots"], queryFn: getFreeSlots });

  const [charId,  setCharId]  = useState<number | "">("");
  const [role,    setRole]    = useState("DPS");
  const [diff,    setDiff]    = useState("HARD");
  const [slot,    setSlot]    = useState("");
  const [members, setMembers] = useState<PartyMemberInput[]>([
    { discord_id: "", role: "DPS" },
    { discord_id: "", role: "DPS" },
    { discord_id: "", role: "SUP" },
  ]);
  const [error, setError] = useState("");

  const create = useMutation({
    mutationFn: () => createSchedule({
      character_id:   charId as number,
      role,
      difficulty:     diff,
      start_time:     slot,
      party_members:  members.filter((m) => m.discord_id.trim()),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedules"] });
      navigate("/dashboard");
    },
    onError: (e: Error) => setError(e.message),
  });

  const updateMember = (i: number, field: keyof PartyMemberInput, val: string) =>
    setMembers((prev) => prev.map((m, idx) => idx === i ? { ...m, [field]: val } : m));

  return (
    <div className="max-w-lg space-y-6">
      <h1 className="text-2xl font-bold">Agendar Party</h1>

      {error && <p className="text-red-400 text-sm bg-red-900/30 px-3 py-2 rounded">{error}</p>}

      <div className="bg-gray-900 rounded-lg p-5 space-y-4">
        {/* Personagem */}
        <div>
          <label className="block text-sm text-gray-400 mb-1">Seu Personagem</label>
          <select
            className="w-full bg-gray-800 rounded px-3 py-2 text-sm"
            value={charId}
            onChange={(e) => setCharId(Number(e.target.value))}
          >
            <option value="">Selecione...</option>
            {characters.map((c) => (
              <option key={c.id} value={c.id}>{c.name}{c.class ? ` (${c.class})` : ""}</option>
            ))}
          </select>
        </div>

        {/* Função */}
        <div>
          <label className="block text-sm text-gray-400 mb-1">Sua Função</label>
          <div className="flex gap-2">
            {ROLES.map((r) => (
              <button
                key={r}
                onClick={() => setRole(r)}
                className={`flex-1 py-2 rounded text-sm font-medium transition-colors ${role === r ? "bg-brand text-white" : "bg-gray-800 text-gray-300 hover:bg-gray-700"}`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        {/* Dificuldade */}
        <div>
          <label className="block text-sm text-gray-400 mb-1">Dificuldade</label>
          <div className="flex gap-2">
            {DIFFICULTIES.map((d) => (
              <button
                key={d}
                onClick={() => setDiff(d)}
                className={`flex-1 py-2 rounded text-sm font-medium transition-colors ${diff === d ? "bg-brand text-white" : "bg-gray-800 text-gray-300 hover:bg-gray-700"}`}
              >
                {d}
              </button>
            ))}
          </div>
        </div>

        {/* Horário */}
        <div>
          <label className="block text-sm text-gray-400 mb-1">Horário (blocos livres de 3h)</label>
          <select
            className="w-full bg-gray-800 rounded px-3 py-2 text-sm"
            value={slot}
            onChange={(e) => setSlot(e.target.value)}
          >
            <option value="">Selecione um horário...</option>
            {slots.map((s) => (
              <option key={s.start} value={s.start}>
                {new Date(s.start).toLocaleString("pt-BR")} → {new Date(s.end).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
              </option>
            ))}
          </select>
        </div>

        {/* Membros da party */}
        <div>
          <label className="block text-sm text-gray-400 mb-2">Outros membros da party</label>
          <div className="space-y-2">
            {members.map((m, i) => (
              <div key={i} className="flex gap-2">
                <input
                  className="bg-gray-800 rounded px-3 py-2 text-sm flex-1"
                  placeholder={`Discord ID do membro ${i + 2}`}
                  value={m.discord_id}
                  onChange={(e) => updateMember(i, "discord_id", e.target.value)}
                />
                <select
                  className="bg-gray-800 rounded px-2 py-2 text-sm"
                  value={m.role}
                  onChange={(e) => updateMember(i, "role", e.target.value)}
                >
                  {ROLES.map((r) => <option key={r}>{r}</option>)}
                </select>
              </div>
            ))}
          </div>
        </div>

        <button
          onClick={() => create.mutate()}
          disabled={!charId || !slot || create.isPending}
          className="w-full bg-brand hover:bg-brand-dark disabled:opacity-40 text-white font-semibold py-2.5 rounded transition-colors"
        >
          {create.isPending ? "Agendando..." : "Confirmar Agendamento"}
        </button>
      </div>
    </div>
  );
}

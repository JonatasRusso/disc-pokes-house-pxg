import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getCharacters, getFreeSlots, getMembers, createSchedule } from "../lib/api";
import { useAuth } from "../lib/useAuth";
import WeeklySlots from "../components/WeeklySlots";
import MemberPicker, { PartyMemberInput } from "../components/MemberPicker";

const ROLES = ["DPS", "SUP", "TANK"] as const;
const DIFFICULTIES = ["HARD", "NW"] as const;

export default function Agendar() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc       = useQueryClient();

  const { data: characters = [] } = useQuery({ queryKey: ["characters"], queryFn: getCharacters });
  const { data: slots      = [] } = useQuery({ queryKey: ["free-slots"], queryFn: getFreeSlots });
  const { data: members    = [] } = useQuery({ queryKey: ["members"],    queryFn: getMembers });

  const [charId, setCharId] = useState<number | "">("");
  const [role,   setRole]   = useState("DPS");
  const [diff,   setDiff]   = useState("HARD");
  const [slot,   setSlot]   = useState("");
  const [party,  setParty]  = useState<PartyMemberInput[]>([
    { discord_id: "", role: "DPS", character_id: null },
    { discord_id: "", role: "SUP", character_id: null },
    { discord_id: "", role: "TANK", character_id: null },
  ]);
  const [error, setError] = useState("");

  const create = useMutation({
    mutationFn: () => createSchedule({
      character_id:  charId as number,
      role,
      difficulty:    diff,
      start_time:    slot,
      party_members: party.filter((m) => m.discord_id),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedules"] });
      qc.invalidateQueries({ queryKey: ["members"] });
      navigate("/dashboard");
    },
    onError: (e: Error) => setError(e.message),
  });

  function validateAndSubmit() {
    setError("");
    // Membros que selecionaram alguém mas têm personagem livre devem escolher um
    for (const m of party) {
      if (!m.discord_id) continue;
      const mem = members.find((x) => x.discord_id === m.discord_id);
      if (mem && mem.characters.length > 0 && m.character_id === null) {
        setError(`Selecione o personagem de ${mem.username}.`);
        return;
      }
    }
    create.mutate();
  }

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-bold">Agendar Party</h1>

      {error && <p className="text-red-400 text-sm bg-red-900/30 px-3 py-2 rounded">{error}</p>}

      <div className="bg-gray-900 rounded-lg p-5 space-y-5">
        {/* Personagem do criador */}
        <div>
          <label className="block text-sm text-gray-400 mb-1">Seu Personagem</label>
          <select
            className="w-full max-w-sm bg-gray-800 rounded px-3 py-2 text-sm"
            value={charId}
            onChange={(e) => setCharId(Number(e.target.value))}
          >
            <option value="">Selecione...</option>
            {characters.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          {characters.length === 0 && (
            <p className="text-xs text-yellow-400 mt-1">
              Você ainda não tem personagens. Cadastre um na aba <strong>Perfil</strong>.
            </p>
          )}
        </div>

        {/* Função + Dificuldade */}
        <div className="flex flex-wrap gap-6">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Sua Função</label>
            <div className="flex gap-2">
              {ROLES.map((r) => (
                <button
                  key={r}
                  onClick={() => setRole(r)}
                  className={`px-4 py-2 rounded text-sm font-medium transition-colors ${role === r ? "bg-brand text-white" : "bg-gray-800 text-gray-300 hover:bg-gray-700"}`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Dificuldade</label>
            <div className="flex gap-2">
              {DIFFICULTIES.map((d) => (
                <button
                  key={d}
                  onClick={() => setDiff(d)}
                  className={`px-4 py-2 rounded text-sm font-medium transition-colors ${diff === d ? "bg-brand text-white" : "bg-gray-800 text-gray-300 hover:bg-gray-700"}`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Planilha semanal de horários */}
        <div>
          <label className="block text-sm text-gray-400 mb-2">
            Horário {slot && <span className="text-brand">— {new Date(slot).toLocaleString("pt-BR")}</span>}
          </label>
          <WeeklySlots slots={slots} selected={slot} onSelect={setSlot} />
        </div>

        {/* Membros da party */}
        <div>
          <label className="block text-sm text-gray-400 mb-2">Membros da party (opcional)</label>
          <MemberPicker
            members={members}
            excludeId={user?.discord_id ?? ""}
            value={party}
            onChange={setParty}
          />
        </div>

        <button
          onClick={validateAndSubmit}
          disabled={!charId || !slot || create.isPending}
          className="w-full bg-brand hover:bg-brand-dark disabled:opacity-40 text-white font-semibold py-2.5 rounded transition-colors"
        >
          {create.isPending ? "Agendando..." : "Confirmar Agendamento"}
        </button>
      </div>
    </div>
  );
}

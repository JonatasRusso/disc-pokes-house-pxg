import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getSchedules, getPokemon, getCharacters, WEEKDAY_LABEL,
  confirmPresence, leaveParty, setMyCharacter, Schedule,
} from "../lib/api";
import { useAuth } from "../lib/useAuth";
import { Link } from "react-router-dom";
import { useState } from "react";

const STATUS_COLOR: Record<string, string> = {
  pending:     "bg-yellow-600",
  confirmed:   "bg-green-600",
  rescheduled: "bg-blue-600",
  missed:      "bg-red-700",
  cancelled:   "bg-gray-600",
};

const ROLE_COLOR: Record<string, string> = {
  TANK: "text-blue-400",
  SUP:  "text-green-400",
  DPS:  "text-red-400",
};

const POKE_CATEGORY: Record<string, string> = { A: "Tank", B: "DPS", C: "Sup" };

export default function Dashboard() {
  const { user } = useAuth();
  const { data: schedules = [] } = useQuery({ queryKey: ["schedules"], queryFn: getSchedules });
  const { data: pokemon   = [] } = useQuery({ queryKey: ["pokemon"],   queryFn: getPokemon });

  const upcoming = schedules
    .filter((s) => s.status !== "cancelled" && s.status !== "missed")
    .slice(0, 5);

  const myPokemon = pokemon.filter((p) => p.assigned_to === user?.discord_id).slice(0, 6);
  const freePokemon = pokemon.filter((p) => !p.assigned_to).length;

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Olá, {user?.username} 👋</h1>

      {/* Próximos horários */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Próximos Horários</h2>
          <Link to="/agendar" className="text-sm text-brand hover:underline">+ Agendar</Link>
        </div>
        {upcoming.length === 0 ? (
          <p className="text-gray-500 text-sm">Nenhum horário agendado.</p>
        ) : (
          <div className="grid gap-3">
            {upcoming.map((s) => (
              <ScheduleCard key={s.id} schedule={s} myId={user?.discord_id ?? ""} />
            ))}
          </div>
        )}
      </section>

      {/* Resumo pokémons */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Seus Pokémons em Uso</h2>
          {user?.is_admin && (
            <Link to="/admin/pokemon" className="text-sm text-brand hover:underline">Gerenciar</Link>
          )}
        </div>
        <div className="flex items-center gap-4 text-sm text-gray-400 mb-3">
          <span>🟢 {myPokemon.length} em uso por você</span>
          <span>⚪ {freePokemon} livres no servidor</span>
        </div>
        {myPokemon.length === 0 ? (
          <p className="text-gray-500 text-sm">Você não está usando nenhum pokémon.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {myPokemon.map((p) => (
              <span key={p.id} className="bg-gray-800 px-3 py-1 rounded-full text-sm">
                {p.name} <span className="text-gray-500 text-xs">[{POKE_CATEGORY[p.category]}]</span>
              </span>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function ScheduleCard({ schedule: s, myId }: { schedule: Schedule; myId: string }) {
  const qc = useQueryClient();
  const me = s.members.find((m) => m.discord_id === myId);
  const [pickChar, setPickChar] = useState<number | "">("");

  const { data: chars = [] } = useQuery({ queryKey: ["characters"], queryFn: getCharacters });
  const refresh = () => qc.invalidateQueries({ queryKey: ["schedules"] });

  const confirm = useMutation({ mutationFn: () => confirmPresence(s.id), onSuccess: refresh });
  const leave   = useMutation({ mutationFn: () => leaveParty(s.id), onSuccess: refresh });
  const setChar = useMutation({ mutationFn: (cid: number) => setMyCharacter(s.id, cid), onSuccess: refresh });

  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <div className="flex items-center gap-4">
        <span className={`text-xs px-2 py-0.5 rounded-full text-white font-medium ${STATUS_COLOR[s.status]}`}>
          {s.status}
        </span>
        <div>
          <p className="font-medium">
            {s.difficulty} <span className="text-gray-500 text-xs font-normal">· toda semana</span>
            {s.organizer_id === myId && (
              <span className="ml-2 text-[10px] bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded">organizada por você</span>
            )}
          </p>
          <p className="text-gray-400 text-sm">
            🔁 Toda <strong>{WEEKDAY_LABEL[s.weekday]}</strong> {String(s.hour).padStart(2, "0")}:00 → {String((s.hour + 3) % 24).padStart(2, "0")}:00
          </p>
          <p className="text-gray-600 text-xs">Próxima: {new Date(s.start_time).toLocaleDateString("pt-BR")}</p>
        </div>
        <Link to={`/remarcar/${s.id}`} className="ml-auto text-sm text-gray-500 hover:text-orange-400 transition-colors">
          Remarcar
        </Link>
      </div>

      {/* Membros, posições e status */}
      {s.members.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-800 grid grid-cols-2 sm:grid-cols-4 gap-2">
          {s.members.map((m) => (
            <div key={m.discord_id} className="flex flex-col">
              <span className={`text-[10px] font-bold ${ROLE_COLOR[m.role]}`}>{m.role}</span>
              <span className="text-sm">{m.nick}</span>
              <span className="text-xs text-gray-500">{m.character ?? "⚠️ sem personagem"}</span>
              <span className={`text-[10px] ${m.confirmed ? "text-green-400" : "text-yellow-500"}`}>
                {m.confirmed ? "✅ confirmou" : "⏳ pendente"}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Ações do usuário (se for membro) */}
      {me && (
        <div className="mt-3 pt-3 border-t border-gray-800 flex flex-wrap items-center gap-2">
          {!me.character ? (
            <div className="flex items-center gap-2">
              <select
                className="bg-gray-800 rounded px-2 py-1 text-sm"
                value={pickChar}
                onChange={(e) => setPickChar(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="">Definir meu personagem...</option>
                {chars.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <button
                onClick={() => pickChar && setChar.mutate(pickChar as number)}
                disabled={!pickChar || setChar.isPending}
                className="bg-brand hover:bg-brand-dark disabled:opacity-40 text-white text-xs px-3 py-1 rounded"
              >
                Salvar
              </button>
            </div>
          ) : me.confirmed ? (
            <span className="text-green-400 text-sm">✅ Você confirmou presença</span>
          ) : (
            <button
              onClick={() => confirm.mutate()}
              disabled={confirm.isPending}
              className="bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white text-xs px-3 py-1 rounded"
            >
              Confirmar presença
            </button>
          )}

          <button
            onClick={() => { if (window.confirm("Sair desta PT?")) leave.mutate(); }}
            disabled={leave.isPending}
            className="ml-auto text-red-500 hover:text-red-400 text-xs hover:underline"
          >
            Sair da PT
          </button>
        </div>
      )}

      {(confirm.isError || leave.isError || setChar.isError) && (
        <p className="mt-2 text-red-400 text-xs">
          {((confirm.error || leave.error || setChar.error) as Error | null)?.message}
        </p>
      )}
    </div>
  );
}

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  getSchedules, getCharacters, getMembers, WEEKDAY_LABEL, Schedule, Role, ROLE_CAPACITY,
  confirmPresence, leaveParty, setMyCharacter, cancelSchedule,
  promoteColeader, kickMember, addMember, setMemberExternal,
} from "../lib/api";
import { useAuth } from "../lib/useAuth";

const STATUS_COLOR: Record<string, string> = {
  pending: "bg-yellow-600", confirmed: "bg-green-600", rescheduled: "bg-blue-600",
  missed: "bg-red-700", cancelled: "bg-gray-600",
};
const ROLE_COLOR: Record<string, string> = {
  TANK: "text-blue-400", SUP: "text-green-400", DPS: "text-red-400",
};

export default function MinhasPTs() {
  const { user } = useAuth();
  const { data: schedules = [], isLoading } = useQuery({ queryKey: ["schedules"], queryFn: getSchedules });

  const active = schedules.filter((s) => s.status !== "cancelled" && s.status !== "missed");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">💀 Minhas PTs</h1>
        <Link to="/agendar" className="text-sm text-brand hover:underline">+ Agendar</Link>
      </div>

      {isLoading ? (
        <p className="text-gray-500 text-sm">Carregando...</p>
      ) : active.length === 0 ? (
        <p className="text-gray-500 text-sm">Você não está em nenhuma PT.</p>
      ) : (
        <div className="grid gap-3">
          {active.map((s) => <PTCard key={s.id} schedule={s} myId={user?.discord_id ?? ""} />)}
        </div>
      )}
    </div>
  );
}

function PTCard({ schedule: s, myId }: { schedule: Schedule; myId: string }) {
  const qc = useQueryClient();
  const me = s.members.find((m) => m.discord_id === myId);

  // Composição alvo 1 TANK / 2 DPS / 1 SUP — papéis que faltam para completar a PT
  const counts: Record<Role, number> = { TANK: 0, DPS: 0, SUP: 0 };
  s.members.forEach((m) => { counts[m.role]++; });
  const missing: Role[] = (["TANK", "DPS", "SUP"] as Role[])
    .flatMap((r) => Array(Math.max(0, ROLE_CAPACITY[r] - counts[r])).fill(r));
  const [pickChar, setPickChar] = useState<number | "">("");
  const { data: chars = [] } = useQuery({ queryKey: ["characters"], queryFn: getCharacters });
  const refresh = () => qc.invalidateQueries({ queryKey: ["schedules"] });

  const confirm = useMutation({ mutationFn: () => confirmPresence(s.id), onSuccess: refresh });
  const leave   = useMutation({ mutationFn: () => leaveParty(s.id), onSuccess: refresh });
  const setChar = useMutation({ mutationFn: (cid: number) => setMyCharacter(s.id, cid), onSuccess: refresh });
  const cancel  = useMutation({ mutationFn: () => cancelSchedule(s.id), onSuccess: refresh });
  const promote = useMutation({ mutationFn: (v: { uid: string; co: boolean }) => promoteColeader(s.id, v.uid, v.co), onSuccess: refresh });
  const kick    = useMutation({ mutationFn: (uid: string) => kickMember(s.id, uid), onSuccess: refresh });
  const setExt  = useMutation({ mutationFn: (v: { uid: string; ext: boolean }) => setMemberExternal(s.id, v.uid, v.ext), onSuccess: refresh });

  const err = (confirm.error || leave.error || setChar.error || cancel.error || promote.error || kick.error || setExt.error) as Error | null;

  return (
    <div className="bg-gray-900 rounded-lg p-4">
      {/* Cabeçalho */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className={`text-xs px-2 py-0.5 rounded-full text-white font-medium ${STATUS_COLOR[s.status]}`}>{s.status}</span>
        <div>
          <p className="font-medium">
            {s.difficulty} <span className="text-gray-500 text-xs font-normal">· toda semana</span>
            {s.is_leader && <span className="ml-2 text-[10px] bg-brand text-white px-1.5 py-0.5 rounded">você é líder</span>}
          </p>
          <p className="text-gray-400 text-sm">
            🔁 Toda <strong>{WEEKDAY_LABEL[s.weekday]}</strong> {String(s.hour).padStart(2, "0")}:00 → {String((s.hour + 3) % 24).padStart(2, "0")}:00
          </p>
          {s.is_override ? (
            <p className="text-amber-400 text-xs">
              📌 Esta semana: <strong>{new Date(s.start_time).toLocaleString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</strong>
              <span className="text-gray-500"> — volta ao normal depois</span>
            </p>
          ) : (
            <p className="text-gray-600 text-xs">Próxima: {new Date(s.start_time).toLocaleDateString("pt-BR")}</p>
          )}
        </div>
        <div className="ml-auto flex gap-3 text-sm">
          {s.can_manage && <Link to={`/remarcar/${s.id}`} className="text-gray-400 hover:text-orange-400">Remarcar</Link>}
          {s.can_manage && (
            <button onClick={() => { if (window.confirm("Cancelar a PT inteira?")) cancel.mutate(); }} className="text-red-500 hover:text-red-400">Cancelar PT</button>
          )}
        </div>
      </div>

      {/* Membros */}
      {s.members.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-800 grid grid-cols-1 sm:grid-cols-2 gap-2">
          {s.members.map((m) => {
            const isLeaderMember = m.discord_id === s.organizer_id;
            return (
              <div key={m.discord_id} className="flex items-center gap-2 bg-gray-800/50 rounded px-2 py-1.5">
                <div className="flex flex-col min-w-0">
                  <span className="text-sm truncate">
                    <span className={`font-bold ${ROLE_COLOR[m.role]} mr-1`}>{m.role}</span>
                    {m.nick}
                    {isLeaderMember && <span className="ml-1 text-[10px] text-brand">👑</span>}
                    {m.is_coleader && <span className="ml-1 text-[10px] text-amber-400">co-líder</span>}
                    {m.is_guest && <span className="ml-1 text-[10px] text-sky-400">convidado</span>}
                  </span>
                  <span className="text-xs text-gray-500 truncate">
                    {m.is_external ? "🌐 usa pokémon próprio (outro servidor)" : (m.character ?? "⚠️ sem personagem")}
                  </span>
                </div>
                <div className="ml-auto flex items-center gap-2 shrink-0">
                  {m.is_guest ? (
                    // Convidado de outro servidor Discord — não está aqui pra confirmar
                    <span className="text-[10px] text-sky-400">convidado</span>
                  ) : (
                    // Externo de jogo confirma normalmente (é alertado do início da PT)
                    <span className={`text-[10px] ${m.confirmed ? "text-green-400" : "text-yellow-500"}`}>
                      {m.confirmed ? "✅" : "⏳"}
                    </span>
                  )}
                  {/* Qualquer membro da PT marca outro como "usa pokémon próprio". Convidado é fixo. */}
                  {s.is_member && !m.is_guest && (
                    <button
                      onClick={() => setExt.mutate({ uid: m.discord_id, ext: !m.is_external })}
                      disabled={setExt.isPending}
                      title={m.is_external
                        ? "Desmarcar: volta a usar os pokémon da house"
                        : "Marcar: usa pokémon próprio (não os da house)"}
                      className={`text-[11px] leading-none ${m.is_external ? "text-sky-400" : "text-gray-600 hover:text-sky-400"}`}
                    >
                      🌐
                    </button>
                  )}
                </div>
                {/* Ações de gestão (líder/co-líder), exceto sobre o líder */}
                {s.can_manage && !isLeaderMember && m.discord_id !== myId && (
                  <div className="flex gap-1 shrink-0">
                    {s.is_leader && !m.is_external && (
                      <button
                        onClick={() => promote.mutate({ uid: m.discord_id, co: !m.is_coleader })}
                        className="text-[10px] text-amber-400 hover:underline"
                        title="Promover/rebaixar co-líder"
                      >
                        {m.is_coleader ? "−co" : "+co"}
                      </button>
                    )}
                    <button onClick={() => { if (window.confirm(`Remover ${m.nick}?`)) kick.mutate(m.discord_id); }} className="text-[10px] text-red-500 hover:underline">remover</button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Adicionar membros (PT incompleta) — líder/co-líder */}
      {s.can_manage && missing.length > 0 && (
        <AddMembers
          scheduleId={s.id}
          missing={missing}
          currentIds={s.members.map((m) => m.discord_id)}
        />
      )}

      {/* Ações próprias */}
      {me && (
        <div className="mt-3 pt-3 border-t border-gray-800 flex flex-wrap items-center gap-2">
          {!me.character ? (
            <div className="flex items-center gap-2">
              <select className="bg-gray-800 rounded px-2 py-1 text-sm" value={pickChar}
                onChange={(e) => setPickChar(e.target.value ? Number(e.target.value) : "")}>
                <option value="">Definir meu personagem...</option>
                {chars.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <button onClick={() => pickChar && setChar.mutate(pickChar as number)} disabled={!pickChar || setChar.isPending}
                className="bg-brand hover:bg-brand-dark disabled:opacity-40 text-white text-xs px-3 py-1 rounded">Salvar</button>
            </div>
          ) : me.confirmed ? (
            <span className="text-green-400 text-sm">✅ Você confirmou presença</span>
          ) : (
            <button onClick={() => confirm.mutate()} disabled={confirm.isPending}
              className="bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white text-xs px-3 py-1 rounded">Confirmar presença</button>
          )}
          <button onClick={() => { if (window.confirm("Sair desta PT?")) leave.mutate(); }} disabled={leave.isPending}
            className="ml-auto text-red-500 hover:text-red-400 text-xs hover:underline">Sair da PT</button>
        </div>
      )}

      {err && <p className="mt-2 text-red-400 text-xs">{err.message}</p>}
    </div>
  );
}

type AddRow = { external: boolean; discord_id: string; character_id: number | ""; name: string };

const EMPTY_ROW: AddRow = { external: false, discord_id: "", character_id: "", name: "" };

function AddMembers({ scheduleId, missing, currentIds }: { scheduleId: number; missing: Role[]; currentIds: string[] }) {
  const qc = useQueryClient();
  const { data: members = [] } = useQuery({ queryKey: ["members"], queryFn: getMembers });
  const add = useMutation({
    mutationFn: (b: { discord_id?: string; external_name?: string; role: string; character_id: number | null }) => addMember(scheduleId, b),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedules"] });
      qc.invalidateQueries({ queryKey: ["members"] });
    },
  });

  const [rows, setRows] = useState<Record<number, AddRow>>({});
  const setRow = (i: number, patch: Partial<AddRow>) =>
    setRows((prev) => ({ ...prev, [i]: { ...(prev[i] ?? EMPTY_ROW), ...patch } }));

  const available = members.filter((m) => !currentIds.includes(m.discord_id));

  return (
    <div className="mt-3 pt-3 border-t border-gray-800 space-y-2">
      <p className="text-xs text-amber-400">
        ⚠️ PT incompleta — faltam: <strong>{missing.join(", ")}</strong>
      </p>
      {missing.map((role, i) => {
        const cur = rows[i] ?? EMPTY_ROW;
        const selMember = members.find((m) => m.discord_id === cur.discord_id);
        const needChar  = !cur.external && !!selMember && selMember.characters.length > 0;
        const noChar    = !cur.external && !!selMember && selMember.characters.length === 0;
        const canAdd    = cur.external
          ? cur.name.trim() !== "" && !add.isPending
          : !!cur.discord_id && !add.isPending && (!needChar || cur.character_id !== "");
        return (
          <div key={i} className="flex flex-wrap items-center gap-2 bg-gray-800/50 rounded px-2 py-1.5">
            <span className={`text-xs font-bold ${ROLE_COLOR[role]}`}>{role}</span>

            {cur.external ? (
              <input
                type="text"
                placeholder={`Nome do ${role} (convidado de fora)...`}
                value={cur.name}
                onChange={(e) => setRow(i, { name: e.target.value })}
                className="bg-gray-900 rounded px-2 py-1 text-sm"
              />
            ) : (
              <>
                <select
                  className="bg-gray-900 rounded px-2 py-1 text-sm"
                  value={cur.discord_id}
                  onChange={(e) => setRow(i, { discord_id: e.target.value, character_id: "" })}
                >
                  <option value="">Adicionar {role}...</option>
                  {available.map((m) => <option key={m.discord_id} value={m.discord_id}>{m.username}</option>)}
                </select>
                {needChar && (
                  <select
                    className="bg-gray-900 rounded px-2 py-1 text-sm"
                    value={cur.character_id}
                    onChange={(e) => setRow(i, { character_id: e.target.value ? Number(e.target.value) : "" })}
                  >
                    <option value="">Personagem...</option>
                    {selMember!.characters.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                )}
                {noChar && <span className="text-[11px] text-yellow-400">sem personagem livre — será convidado(a)</span>}
              </>
            )}

            <label className="flex items-center gap-1 text-[11px] text-gray-400 cursor-pointer">
              <input
                type="checkbox"
                checked={cur.external}
                onChange={(e) => setRow(i, { external: e.target.checked, discord_id: "", character_id: "", name: "" })}
                className="accent-sky-500"
              />
              convidado de fora
            </label>

            <button
              disabled={!canAdd}
              onClick={() => add.mutate(cur.external
                ? { external_name: cur.name.trim(), role, character_id: null }
                : { discord_id: cur.discord_id, role, character_id: cur.character_id === "" ? null : cur.character_id })}
              className="bg-brand hover:bg-brand-dark disabled:opacity-40 text-white text-xs px-3 py-1 rounded"
            >
              Adicionar
            </button>
          </div>
        );
      })}
      <p className="text-[11px] text-gray-500">
        <strong>Convidado de fora</strong> = quem não está no Discord da house (só nome; não recebe avisos).
        Quem <em>está</em> no Discord mas usa pokémon próprio: adicione normal e marque o 🌐 no membro.
      </p>
      {add.error && <p className="text-red-400 text-xs">{(add.error as Error).message}</p>}
    </div>
  );
}

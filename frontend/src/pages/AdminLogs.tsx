import { useQuery } from "@tanstack/react-query";
import { getHistory, HistoryEntry } from "../lib/api";
import { useState } from "react";

const ENTITY_TYPES = ["", "schedule", "pokemon", "admin", "party"];

const ACTION_COLOR: Record<string, string> = {
  created:       "bg-blue-900 text-blue-300",
  confirmed:     "bg-green-900 text-green-300",
  rescheduled:   "bg-yellow-900 text-yellow-300",
  missed:        "bg-red-900 text-red-300",
  cancelled:     "bg-gray-800 text-gray-400",
  assigned:      "bg-purple-900 text-purple-300",
  unassigned:    "bg-gray-800 text-gray-400",
  overridden:    "bg-orange-900 text-orange-300",
  admin_granted: "bg-brand/20 text-brand",
  admin_revoked: "bg-red-900 text-red-400",
  admin_edited:  "bg-yellow-900 text-yellow-300",
};

export default function AdminLogs() {
  const [filter, setFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const LIMIT = 50;

  const { data: logs = [], isLoading } = useQuery({
    queryKey: ["history", filter, offset],
    queryFn:  () => getHistory({ entity_type: filter || undefined, limit: LIMIT, offset }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Admin — Logs de Atividade</h1>
      <p className="text-gray-400 text-sm">Histórico completo de todas as ações. Somente leitura.</p>

      <div className="flex gap-3 items-center">
        <select
          className="bg-gray-900 rounded px-3 py-2 text-sm border border-gray-800"
          value={filter}
          onChange={(e) => { setFilter(e.target.value); setOffset(0); }}
        >
          {ENTITY_TYPES.map((t) => (
            <option key={t} value={t}>{t || "Todos os tipos"}</option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <p className="text-gray-500 text-sm">Carregando...</p>
      ) : (
        <div className="space-y-2">
          {logs.map((h) => <LogRow key={h.id} entry={h} />)}
          {logs.length === 0 && <p className="text-gray-500 text-sm">Nenhum log encontrado.</p>}
        </div>
      )}

      {/* Paginação simples */}
      <div className="flex gap-3 text-sm">
        <button
          onClick={() => setOffset(Math.max(0, offset - LIMIT))}
          disabled={offset === 0}
          className="text-gray-400 hover:text-white disabled:opacity-30"
        >
          ← Anterior
        </button>
        <button
          onClick={() => setOffset(offset + LIMIT)}
          disabled={logs.length < LIMIT}
          className="text-gray-400 hover:text-white disabled:opacity-30"
        >
          Próximo →
        </button>
      </div>
    </div>
  );
}

function LogRow({ entry: h }: { entry: HistoryEntry }) {
  const colorClass = ACTION_COLOR[h.action] ?? "bg-gray-800 text-gray-400";
  return (
    <div className="bg-gray-900 rounded-lg px-4 py-3 flex items-center gap-3 text-sm">
      <span className="text-gray-600 w-16 shrink-0">#{h.id}</span>
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${colorClass}`}>{h.action}</span>
      <span className="text-gray-500 shrink-0">{h.entity_type} {h.entity_id ? `#${h.entity_id}` : ""}</span>
      {h.detail && <span className="text-gray-600 text-xs font-mono truncate">{h.detail}</span>}
      <span className="ml-auto text-gray-600 text-xs shrink-0 whitespace-nowrap">
        {new Date(h.happened_at).toLocaleString("pt-BR")}
      </span>
    </div>
  );
}

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { getFreeSlots, getCalendar, reschedule } from "../lib/api";
import { useState } from "react";
import WeeklySlots from "../components/WeeklySlots";

type Scope = "once" | "all";

export default function Remarcar() {
  const { id }    = useParams<{ id: string }>();
  const navigate  = useNavigate();
  const qc        = useQueryClient();
  const scheduleId = Number(id);

  const [params] = useSearchParams();
  const initialScope: Scope = params.get("scope") === "all" ? "all" : "once";

  // Grade ignorando a PRÓPRIA PT → o slot atual dela fica livre para manter/ajustar.
  const { data: slots   = [] } = useQuery({ queryKey: ["free-slots", scheduleId], queryFn: () => getFreeSlots(scheduleId) });
  const { data: parties = [] } = useQuery({ queryKey: ["calendar"],   queryFn: getCalendar });
  const otherParties = parties.filter((p) => p.schedule_id !== scheduleId);

  const [slot,      setSlot]      = useState("");
  const [scope,     setScope]     = useState<Scope>(initialScope);
  const [overwrite, setOverwrite] = useState(false);
  const [error,     setError]     = useState("");

  const doReschedule = useMutation({
    mutationFn: () => reschedule(scheduleId, slot, scope, overwrite),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedules"] });
      qc.invalidateQueries({ queryKey: ["calendar"] });
      navigate("/minhas-pts");
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-bold">Remarcar Horário #{scheduleId}</h1>
      <p className="text-gray-400 text-sm">
        Escolha o tipo de remarcação e o novo horário. Os outros membros da PT serão notificados automaticamente.
      </p>

      {error && <p className="text-red-400 text-sm bg-red-900/30 px-3 py-2 rounded">{error}</p>}

      {/* Tipo de remarcação */}
      <div className="grid sm:grid-cols-2 gap-3">
        <ScopeCard
          active={scope === "once"}
          onClick={() => setScope("once")}
          icon="📅"
          title="Só esta semana"
          desc="Move apenas a próxima ocorrência. Na semana seguinte volta ao horário de sempre."
        />
        <ScopeCard
          active={scope === "all"}
          onClick={() => setScope("all")}
          icon="🔁"
          title="Todas as semanas"
          desc="Muda o horário fixo da PT a partir de agora (recorrência semanal)."
        />
      </div>

      <div className="bg-gray-900 rounded-lg p-5 space-y-4">
        <label className="block text-sm text-gray-400">
          Novo horário {slot && <span className="text-brand">— {new Date(slot).toLocaleString("pt-BR")}</span>}
        </label>
        <WeeklySlots slots={slots} selected={slot} onSelect={setSlot} parties={otherParties} allowOccupied={overwrite} />

        {/* Sobrescrever outra PT */}
        <label className="flex items-center gap-2 text-sm bg-gray-800/60 rounded px-3 py-2 cursor-pointer w-fit">
          <input
            type="checkbox"
            checked={overwrite}
            onChange={(e) => setOverwrite(e.target.checked)}
            className="accent-orange-500"
          />
          <span>
            Permitir sobrescrever <strong>outra PT</strong>
            <span className="text-gray-500"> — libera os horários já ocupados na grade (duas PTs no mesmo horário)</span>
          </span>
        </label>

        <button
          onClick={() => doReschedule.mutate()}
          disabled={!slot || doReschedule.isPending}
          className="w-full bg-orange-600 hover:bg-orange-700 disabled:opacity-40 text-white font-semibold py-2.5 rounded transition-colors"
        >
          {doReschedule.isPending
            ? "Remarcando..."
            : scope === "once"
              ? "Confirmar — só esta semana"
              : "Confirmar — todas as semanas"}
        </button>
      </div>
    </div>
  );
}

function ScopeCard(props: {
  active: boolean; onClick: () => void; icon: string; title: string; desc: string;
}) {
  return (
    <button
      onClick={props.onClick}
      className={`text-left rounded-lg p-4 border transition-colors ${
        props.active
          ? "border-orange-500 bg-orange-500/10"
          : "border-gray-700 bg-gray-900 hover:border-gray-600"
      }`}
    >
      <p className="font-medium">
        {props.icon} {props.title}
        {props.active && <span className="ml-2 text-[10px] text-orange-400">selecionado</span>}
      </p>
      <p className="text-gray-400 text-xs mt-1">{props.desc}</p>
    </button>
  );
}

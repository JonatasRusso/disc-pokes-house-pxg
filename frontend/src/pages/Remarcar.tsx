import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import { getFreeSlots, getCalendar, reschedule } from "../lib/api";
import { useState } from "react";
import WeeklySlots from "../components/WeeklySlots";

export default function Remarcar() {
  const { id }    = useParams<{ id: string }>();
  const navigate  = useNavigate();
  const qc        = useQueryClient();
  const scheduleId = Number(id);

  const { data: slots   = [] } = useQuery({ queryKey: ["free-slots"], queryFn: getFreeSlots });
  const { data: parties = [] } = useQuery({ queryKey: ["calendar"],   queryFn: getCalendar });
  const [slot,  setSlot]  = useState("");
  const [error, setError] = useState("");

  const doReschedule = useMutation({
    mutationFn: () => reschedule(scheduleId, slot),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedules"] });
      navigate("/dashboard");
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-bold">Remarcar Horário #{scheduleId}</h1>
      <p className="text-gray-400 text-sm">
        Escolha um novo horário. Os outros 3 membros da party serão notificados automaticamente.
      </p>

      {error && <p className="text-red-400 text-sm bg-red-900/30 px-3 py-2 rounded">{error}</p>}

      <div className="bg-gray-900 rounded-lg p-5 space-y-4">
        <label className="block text-sm text-gray-400">
          Novo horário {slot && <span className="text-brand">— {new Date(slot).toLocaleString("pt-BR")}</span>}
        </label>
        <WeeklySlots slots={slots} selected={slot} onSelect={setSlot} parties={parties} />

        <button
          onClick={() => doReschedule.mutate()}
          disabled={!slot || doReschedule.isPending}
          className="w-full bg-orange-600 hover:bg-orange-700 disabled:opacity-40 text-white font-semibold py-2.5 rounded transition-colors"
        >
          {doReschedule.isPending ? "Remarcando..." : "Confirmar Remarcação"}
        </button>
      </div>
    </div>
  );
}

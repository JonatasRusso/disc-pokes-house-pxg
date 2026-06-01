import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import { getFreeSlots, reschedule } from "../lib/api";
import { useState } from "react";

export default function Remarcar() {
  const { id }    = useParams<{ id: string }>();
  const navigate  = useNavigate();
  const qc        = useQueryClient();
  const scheduleId = Number(id);

  const { data: slots = [] } = useQuery({ queryKey: ["free-slots"], queryFn: getFreeSlots });
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
    <div className="max-w-md space-y-6">
      <h1 className="text-2xl font-bold">Remarcar Horário #{scheduleId}</h1>
      <p className="text-gray-400 text-sm">
        Escolha um novo horário. Os outros 3 membros da party serão notificados automaticamente.
      </p>

      {error && <p className="text-red-400 text-sm bg-red-900/30 px-3 py-2 rounded">{error}</p>}

      <div className="bg-gray-900 rounded-lg p-5 space-y-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Novo horário disponível</label>
          <select
            className="w-full bg-gray-800 rounded px-3 py-2 text-sm"
            value={slot}
            onChange={(e) => setSlot(e.target.value)}
          >
            <option value="">Selecione...</option>
            {slots.map((s) => (
              <option key={s.start} value={s.start}>
                {new Date(s.start).toLocaleString("pt-BR")} → {new Date(s.end).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
              </option>
            ))}
          </select>
        </div>

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

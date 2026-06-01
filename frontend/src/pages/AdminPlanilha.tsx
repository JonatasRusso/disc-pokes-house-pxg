import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSchedules, cancelSchedule, Schedule } from "../lib/api";
import { useState } from "react";

const STATUS_COLOR: Record<string, string> = {
  pending:     "text-yellow-400",
  confirmed:   "text-green-400",
  rescheduled: "text-blue-400",
  missed:      "text-red-400",
  cancelled:   "text-gray-500",
};

export default function AdminPlanilha() {
  const qc = useQueryClient();
  const { data: schedules = [], isLoading } = useQuery({ queryKey: ["schedules-all"], queryFn: getSchedules });

  const cancel = useMutation({
    mutationFn: cancelSchedule,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules-all"] }),
  });

  if (isLoading) return <p className="text-gray-500">Carregando...</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Admin — Planilha de Horários</h1>
      <p className="text-gray-400 text-sm">Visualização e gestão de todos os agendamentos. Somente admins podem cancelar horários de outros usuários.</p>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-gray-800">
              <th className="pb-2 pr-4">ID</th>
              <th className="pb-2 pr-4">Dificuldade</th>
              <th className="pb-2 pr-4">Início</th>
              <th className="pb-2 pr-4">Fim</th>
              <th className="pb-2 pr-4">Status</th>
              <th className="pb-2">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-900">
            {schedules.map((s) => (
              <tr key={s.id} className="hover:bg-gray-900/50">
                <td className="py-2 pr-4 text-gray-400">#{s.id}</td>
                <td className="py-2 pr-4 font-medium">{s.difficulty}</td>
                <td className="py-2 pr-4 text-gray-300">{new Date(s.start_time).toLocaleString("pt-BR")}</td>
                <td className="py-2 pr-4 text-gray-300">{new Date(s.end_time).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</td>
                <td className={`py-2 pr-4 font-medium ${STATUS_COLOR[s.status]}`}>{s.status}</td>
                <td className="py-2">
                  {s.status !== "cancelled" && (
                    <button
                      onClick={() => cancel.mutate(s.id)}
                      className="text-red-500 hover:text-red-400 text-xs hover:underline"
                    >
                      Cancelar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {schedules.length === 0 && <p className="text-gray-500 py-4 text-sm">Nenhum horário cadastrado.</p>}
      </div>
    </div>
  );
}

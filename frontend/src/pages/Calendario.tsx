import { useQuery } from "@tanstack/react-query";
import { getFreeSlots, getCalendar } from "../lib/api";
import WeeklySlots from "../components/WeeklySlots";

export default function Calendario() {
  const { data: slots   = [] } = useQuery({ queryKey: ["free-slots"], queryFn: () => getFreeSlots() });
  const { data: parties = [] } = useQuery({ queryKey: ["calendar"],   queryFn: getCalendar });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">📅 Calendário de PTs</h1>
      <p className="text-gray-400 text-sm">
        Visão semanal de todas as PTs marcadas. Passe o mouse numa PT para ver os membros.
      </p>
      {/* Calendário só de visualização: onSelect vazio */}
      <WeeklySlots slots={slots} selected="" onSelect={() => {}} parties={parties} />
    </div>
  );
}

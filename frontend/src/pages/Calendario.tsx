import { useQuery } from "@tanstack/react-query";
import { getCalendar } from "../lib/api";
import { qk } from "../lib/queryKeys";
import WeekCalendar from "../components/WeekCalendar";

export default function Calendario() {
  const { data: parties = [] } = useQuery({ queryKey: qk.calendar, queryFn: getCalendar });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">📅 Calendário de PTs</h1>
      <p className="text-gray-400 text-sm">
        Visão semanal de todas as PTs. Passe o mouse numa PT para ver os membros.
      </p>
      <WeekCalendar parties={parties} />
    </div>
  );
}

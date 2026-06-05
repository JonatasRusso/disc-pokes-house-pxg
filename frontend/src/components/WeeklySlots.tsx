import { Slot } from "../lib/api";

interface Props {
  slots: Slot[];
  selected: string;
  onSelect: (startIso: string) => void;
}

const WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

export default function WeeklySlots({ slots, selected, onSelect }: Props) {
  // Agrupa slots livres por dia (chave = data ISO yyyy-mm-dd)
  const byDay = new Map<string, Slot[]>();
  for (const s of slots) {
    const d = new Date(s.start);
    const key = d.toISOString().slice(0, 10);
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key)!.push(s);
  }

  const days = Array.from(byDay.keys()).sort();

  if (days.length === 0) {
    return <p className="text-gray-500 text-sm">Nenhum horário livre nos próximos 7 dias.</p>;
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-3">
      {days.map((dayKey) => {
        const date = new Date(dayKey + "T00:00:00");
        const daySlots = byDay.get(dayKey)!;
        return (
          <div key={dayKey} className="bg-gray-900 rounded-lg p-2">
            <div className="text-center mb-2 sticky top-0">
              <p className="text-xs text-gray-500">{WEEKDAYS[date.getDay()]}</p>
              <p className="text-sm font-semibold">{date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })}</p>
            </div>
            <div className="flex flex-col gap-1 max-h-64 overflow-y-auto">
              {daySlots.map((s) => {
                const isSel = s.start === selected;
                const hh = new Date(s.start).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
                return (
                  <button
                    key={s.start}
                    onClick={() => onSelect(s.start)}
                    className={`text-xs py-1 rounded transition-colors ${
                      isSel ? "bg-brand text-white font-semibold" : "bg-gray-800 text-gray-300 hover:bg-gray-700"
                    }`}
                  >
                    {hh}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

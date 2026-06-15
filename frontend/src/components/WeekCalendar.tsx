import { CalendarParty, WEEKDAY_SHORT, fmtTime } from "../lib/api";

const PX_PER_HOUR = 54;

const DIFF_STYLE: Record<string, string> = {
  HARD: "bg-red-600/25 border-red-500/50 text-red-100",
  NW:   "bg-purple-600/25 border-purple-500/50 text-purple-100",
};

const startMinOf = (p: CalendarParty) => p.hour * 60 + (p.minute ?? 0);
const endMinOf   = (p: CalendarParty) => startMinOf(p) + (p.duration_minutes ?? 180);

// Agenda semanal (leitura): eixo de horas + blocos posicionados por minuto e
// dimensionados pela duração. Janela ajustada ao intervalo das PTs.
export default function WeekCalendar({ parties }: { parties: CalendarParty[] }) {
  if (parties.length === 0) {
    return <p className="text-gray-500 text-sm">Nenhuma PT marcada ainda.</p>;
  }

  const winStart = Math.floor(Math.min(...parties.map(startMinOf)) / 60) * 60;
  const winEnd   = Math.ceil(Math.max(...parties.map(endMinOf)) / 60) * 60;
  const height   = ((winEnd - winStart) / 60) * PX_PER_HOUR;

  const hours: number[] = [];
  for (let m = winStart; m <= winEnd; m += 60) hours.push(m);

  const byDay: Record<number, CalendarParty[]> = {};
  parties.forEach((p) => (byDay[p.weekday] ??= []).push(p));

  const top = (m: number) => ((m - winStart) / 60) * PX_PER_HOUR;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-4 text-xs text-gray-400">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-600/40 border border-red-500/50 inline-block" /> HARD</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-purple-600/40 border border-purple-500/50 inline-block" /> NW</span>
        <span>📌 remarcada esta semana</span>
      </div>
      <div className="overflow-auto rounded-lg border border-gray-800 bg-gray-900/40">
        <div className="grid min-w-[760px]" style={{ gridTemplateColumns: "3.5rem repeat(7, 1fr)" }}>
          {/* Cabeçalho */}
          <div className="h-9 border-b border-gray-800 sticky top-0 bg-gray-900 z-10" />
          {WEEKDAY_SHORT.map((d, i) => (
            <div key={i} className="h-9 border-b border-l border-gray-800 flex items-center justify-center text-xs font-semibold text-gray-300 sticky top-0 bg-gray-900 z-10">
              {d}
            </div>
          ))}

          {/* Eixo de horas */}
          <div className="relative" style={{ height }}>
            {hours.map((m) => (
              <div key={m} className="absolute right-1.5 text-[10px] text-gray-500 -translate-y-1/2 tabular-nums" style={{ top: top(m) }}>
                {fmtTime(m)}
              </div>
            ))}
          </div>

          {/* Colunas dos dias */}
          {[0, 1, 2, 3, 4, 5, 6].map((wd) => (
            <div key={wd} className="relative border-l border-gray-800" style={{ height }}>
              {hours.map((m) => (
                <div key={m} className="absolute left-0 right-0 border-t border-gray-800/40" style={{ top: top(m) }} />
              ))}
              {(byDay[wd] ?? []).map((p) => {
                const blockTop = top(startMinOf(p));
                const blockH = Math.max(24, ((Math.min(endMinOf(p), winEnd) - startMinOf(p)) / 60) * PX_PER_HOUR);
                const members = p.members.map((m) => m.nick).join(", ");
                return (
                  <div
                    key={p.schedule_id}
                    title={`${fmtTime(startMinOf(p))}–${fmtTime(endMinOf(p) % 1440)} ${p.difficulty}\n` +
                      p.members.map((m) => `${m.role}: ${m.nick}`).join("\n")}
                    className={`absolute left-0.5 right-0.5 rounded border px-1 py-0.5 overflow-hidden text-[10px] leading-tight cursor-help ${DIFF_STYLE[p.difficulty] ?? "bg-gray-700/40 border-gray-600"}`}
                    style={{ top: blockTop, height: blockH }}
                  >
                    <div className="font-semibold truncate">
                      {fmtTime(startMinOf(p))} {p.difficulty}{p.is_override && " 📌"}
                    </div>
                    <div className="truncate opacity-80">{members || "—"}</div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

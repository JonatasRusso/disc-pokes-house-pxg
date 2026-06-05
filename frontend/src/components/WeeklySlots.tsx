import { Slot, CalendarParty } from "../lib/api";

interface Props {
  slots: Slot[];
  selected: string;
  onSelect: (startIso: string) => void;
  parties?: CalendarParty[];
}

const WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

function dayKey(iso: string) {
  return iso.slice(0, 10); // yyyy-mm-dd (string ISO local, sem timezone)
}

function hourOf(iso: string) {
  return Number(iso.slice(11, 13)); // HH
}

// Índice começando na segunda-feira (Seg=0 .. Dom=6) a partir do getDay() (Dom=0..Sáb=6)
function mondayIndex(dk: string) {
  return (new Date(dk + "T00:00:00").getDay() + 6) % 7;
}

// weekday no padrão Python (Seg=0 .. Dom=6) a partir do dayKey
function pyWeekday(dk: string) {
  return (new Date(dk + "T00:00:00").getDay() + 6) % 7;
}

interface CellParty { party: CalendarParty; isStart: boolean }

export default function WeeklySlots({ slots, selected, onSelect, parties = [] }: Props) {
  // Dias distintos ordenados começando na segunda-feira
  const days = Array.from(new Set(slots.map((s) => dayKey(s.start)))).sort(
    (a, b) => mondayIndex(a) - mondayIndex(b)
  );

  // Index: dayKey -> hour -> slot
  const grid = new Map<string, Map<number, Slot>>();
  for (const s of slots) {
    const dk = dayKey(s.start);
    if (!grid.has(dk)) grid.set(dk, new Map());
    grid.get(dk)!.set(hourOf(s.start), s);
  }

  // Index de PTs por célula: "weekday-hour" -> {party, isStart}. Cada PT ocupa 3 horas.
  const partyByCell = new Map<string, CellParty>();
  for (const p of parties) {
    for (let off = 0; off < 3; off++) {
      partyByCell.set(`${p.weekday}-${p.hour + off}`, { party: p, isStart: off === 0 });
    }
  }

  if (days.length === 0) {
    return <p className="text-sm text-gray-500">Nenhum horário disponível.</p>;
  }

  const hours = Array.from({ length: 24 }, (_, h) => h);

  return (
    <div className="space-y-2">
    <div className="flex flex-wrap items-center gap-4 text-xs text-gray-400">
      <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-600/40 inline-block" /> disponível</span>
      <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-brand inline-block" /> selecionado</span>
      <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-600/60 inline-block" /> PT marcada</span>
    </div>
    <div className="rounded-lg border border-gray-800 bg-gray-900/50 overflow-hidden">
      <div className="overflow-auto max-h-[26rem] md:max-h-none md:overflow-visible">
        <div
          className="grid min-w-[640px]"
          style={{ gridTemplateColumns: `4rem repeat(${days.length}, minmax(0, 1fr))` }}
        >
          {/* Cabeçalho: canto + dias da semana */}
          <div className="sticky top-0 z-10 bg-gray-900 border-b border-gray-800 h-10" />
          {days.map((dk) => {
            const wd = new Date(dk + "T00:00:00").getDay();
            return (
              <div
                key={dk}
                className="sticky top-0 z-10 bg-gray-900 border-b border-l border-gray-800 h-10 flex items-center justify-center text-xs font-semibold text-gray-300"
              >
                {WEEKDAYS[wd]}
              </div>
            );
          })}

          {/* Linhas por hora */}
          {hours.map((h) => (
            <Row
              key={h}
              hour={h}
              days={days}
              grid={grid}
              partyByCell={partyByCell}
              selected={selected}
              onSelect={onSelect}
            />
          ))}
        </div>
      </div>
    </div>
    </div>
  );
}

function membersTitle(p: CalendarParty): string {
  const head = `PT ${p.difficulty}`;
  const lines = p.members.map((m) => `${m.role}: ${m.nick}${m.character ? ` (${m.character})` : ""}`);
  return [head, ...lines].join("\n");
}

function Row({
  hour, days, grid, partyByCell, selected, onSelect,
}: {
  hour: number;
  days: string[];
  grid: Map<string, Map<number, Slot>>;
  partyByCell: Map<string, CellParty>;
  selected: string;
  onSelect: (iso: string) => void;
}) {
  const label = `${String(hour).padStart(2, "0")}:00`;
  return (
    <>
      <div className="h-9 flex items-center justify-end pr-2 text-[11px] text-gray-500 border-b border-gray-800/60 tabular-nums">
        {label}
      </div>
      {days.map((dk) => {
        const slot = grid.get(dk)?.get(hour);
        const isSel = slot?.start === selected;
        const free = slot?.free;
        const cell = partyByCell.get(`${pyWeekday(dk)}-${hour}`);

        return (
          <div key={dk + hour} className="h-9 border-b border-l border-gray-800/60 p-0.5">
            {cell ? (
              // Célula ocupada por uma PT — mostra quem está nela
              <div
                title={membersTitle(cell.party)}
                className="w-full h-full rounded bg-amber-600/40 text-[10px] leading-tight px-1 overflow-hidden flex flex-col justify-center cursor-help"
              >
                {cell.isStart ? (
                  <>
                    <span className="font-semibold text-amber-200">{cell.party.difficulty}</span>
                    <span className="truncate text-amber-100/80">
                      {cell.party.members.map((m) => m.nick).join(", ") || "PT"}
                    </span>
                  </>
                ) : (
                  <span className="truncate text-amber-100/60">
                    {cell.party.members.map((m) => `${m.role[0]}·${m.nick}`).join("  ")}
                  </span>
                )}
              </div>
            ) : slot ? (
              <button
                disabled={!free}
                title={free ? "Disponível" : "Indisponível"}
                onClick={() => free && onSelect(slot.start)}
                className={[
                  "w-full h-full rounded transition-colors",
                  isSel
                    ? "bg-brand"
                    : free
                    ? "bg-emerald-600/30 hover:bg-emerald-500/50"
                    : "bg-transparent cursor-not-allowed",
                ].join(" ")}
              />
            ) : null}
          </div>
        );
      })}
    </>
  );
}

import { useState } from "react";
import { Slot, CalendarParty } from "../lib/api";

interface Props {
  slots: Slot[];
  selected: string;
  onSelect: (startIso: string) => void;
  parties?: CalendarParty[];
  allowOccupied?: boolean;  // permite selecionar o início de uma PT já marcada (sobrescrever)
}

const WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

function dayKey(iso: string) {
  return iso.slice(0, 10); // yyyy-mm-dd
}

function hourOf(iso: string) {
  return Number(iso.slice(11, 13)); // HH
}

function mondayIndex(dk: string) {
  return (new Date(dk + "T00:00:00").getDay() + 6) % 7;
}

function pyWeekday(dk: string) {
  return (new Date(dk + "T00:00:00").getDay() + 6) % 7;
}

interface CellParty {
  party: CalendarParty;
  isStart: boolean;
}

export default function WeeklySlots({ slots, selected, onSelect, parties = [], allowOccupied = false }: Props) {
  // Filtros locais
  const [diffFilter, setDiffFilter] = useState<"ALL" | "HARD" | "NW">("ALL");
  const [hideNight, setHideNight] = useState(true);
  const [onlyWithParties, setOnlyWithParties] = useState(false);

  // Dias distintos ordenados começando na segunda-feira
  const days = Array.from(new Set(slots.map((s) => dayKey(s.start)))).sort(
    (a, b) => mondayIndex(a) - mondayIndex(b)
  );

  // Filtra as PTs conforme dificuldade
  const filteredParties = parties.filter((p) => {
    if (diffFilter !== "ALL" && p.difficulty !== diffFilter) return false;
    return true;
  });

  // Index: dayKey -> hour -> slot
  const grid = new Map<string, Map<number, Slot>>();
  for (const s of slots) {
    const dk = dayKey(s.start);
    if (!grid.has(dk)) grid.set(dk, new Map());
    grid.get(dk)!.set(hourOf(s.start), s);
  }

  // Index de PTs filtradas por célula: "weekday-hour" -> {party, isStart}. Cada PT ocupa 3 horas.
  const partyByCell = new Map<string, CellParty>();
  for (const p of filteredParties) {
    for (let off = 0; off < 3; off++) {
      partyByCell.set(`${p.weekday}-${p.hour + off}`, { party: p, isStart: off === 0 });
    }
  }

  if (days.length === 0) {
    return <p className="text-sm text-gray-500">Nenhum horário disponível.</p>;
  }

  // Define as horas com PTs para o filtro de "apenas com PTs"
  const hoursWithParties = new Set<number>();
  for (const p of filteredParties) {
    for (let off = 0; off < 3; off++) {
      hoursWithParties.add(p.hour + off);
    }
  }

  const hours = Array.from({ length: 24 }, (_, h) => h).filter((h) => {
    if (hideNight && h < 8) return false;
    if (onlyWithParties && !hoursWithParties.has(h)) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Controles de Filtros e Legenda */}
      <div className="bg-gray-950/60 backdrop-blur-md border border-gray-800/80 rounded-xl p-4 flex flex-wrap gap-6 items-center justify-between shadow-lg">
        {/* Filtros */}
        <div className="flex flex-wrap gap-4 items-center">
          {/* Filtro Dificuldade */}
          <div className="flex bg-gray-900 rounded-lg p-0.5 border border-gray-800/80">
            {(["ALL", "HARD", "NW"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setDiffFilter(mode)}
                className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                  diffFilter === mode
                    ? "bg-brand text-white shadow-md"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                {mode === "ALL" ? "Todos" : mode}
              </button>
            ))}
          </div>

          {/* Checkboxes */}
          <div className="flex gap-4 items-center text-xs text-gray-300">
            <label className="flex items-center gap-2 cursor-pointer hover:text-white select-none">
              <input
                type="checkbox"
                checked={hideNight}
                onChange={(e) => setHideNight(e.target.checked)}
                className="accent-brand rounded bg-gray-800 border-gray-700"
              />
              <span>Ocultar Madrugada (00h - 07h)</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer hover:text-white select-none">
              <input
                type="checkbox"
                checked={onlyWithParties}
                onChange={(e) => setOnlyWithParties(e.target.checked)}
                className="accent-brand rounded bg-gray-800 border-gray-700"
              />
              <span>Apenas com PTs</span>
            </label>
          </div>
        </div>

        {/* Legenda */}
        <div className="flex flex-wrap items-center gap-4 text-xs text-gray-400">
          <span className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded bg-emerald-600/20 border border-emerald-500/30 inline-block shadow-[0_0_8px_rgba(16,185,129,0.1)]" />
            Disponível
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded bg-brand border border-brand/80 inline-block shadow-[0_0_8px_rgba(88,101,242,0.3)]" />
            Selecionado
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded bg-amber-500/20 border border-amber-500/40 inline-block shadow-[0_0_8px_rgba(245,158,11,0.1)]" />
            PT Marcada
          </span>
        </div>
      </div>

      {/* Grid Calendário */}
      <div className="rounded-xl border border-gray-800 bg-gray-950/40 backdrop-blur-md overflow-hidden shadow-2xl">
        <div className="overflow-auto max-h-[36rem]">
          <div
            className="grid min-w-[720px]"
            style={{ gridTemplateColumns: `4.5rem repeat(${days.length}, minmax(0, 1fr))` }}
          >
            {/* Cabeçalho */}
            <div className="sticky top-0 left-0 z-30 bg-gray-950 border-b border-r border-gray-800 h-11" />
            {days.map((dk) => {
              const wd = new Date(dk + "T00:00:00").getDay();
              return (
                <div
                  key={dk}
                  className="sticky top-0 z-20 bg-gray-950/95 backdrop-blur-md border-b border-l border-gray-800 h-11 flex items-center justify-center text-xs font-bold uppercase tracking-wider text-gray-300"
                >
                  {WEEKDAYS[wd]}
                </div>
              );
            })}

            {/* Linhas */}
            {hours.map((h) => (
              <Row
                key={h}
                hour={h}
                days={days}
                grid={grid}
                partyByCell={partyByCell}
                selected={selected}
                onSelect={onSelect}
                allowOccupied={allowOccupied}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({
  hour,
  days,
  grid,
  partyByCell,
  selected,
  onSelect,
  allowOccupied,
}: {
  hour: number;
  days: string[];
  grid: Map<string, Map<number, Slot>>;
  partyByCell: Map<string, CellParty>;
  selected: string;
  onSelect: (iso: string) => void;
  allowOccupied: boolean;
}) {
  const label = `${String(hour).padStart(2, "0")}:00`;
  return (
    <>
      {/* Coluna de Horário fixa */}
      <div className="sticky left-0 z-10 bg-gray-905 border-r border-gray-850 h-10 flex items-center justify-end pr-3 text-[11px] font-semibold text-gray-400 border-b border-gray-800/60 tabular-nums shadow-[4px_0_8px_-4px_rgba(0,0,0,0.4)]">
        {label}
      </div>

      {days.map((dk, dayIdx) => {
        const slot = grid.get(dk)?.get(hour);
        const isSel = slot?.start === selected;
        const free = slot?.free;
        const cell = partyByCell.get(`${pyWeekday(dk)}-${hour}`);

        // PTs na quinta, sexta, sábado e domingo alinham o popover à direita para não cortar
        const alignRight = dayIdx >= 4;

        return (
          <div
            key={dk + hour}
            className="h-10 border-b border-l border-gray-850 p-0.5 relative group transition-all duration-205"
          >
            {cell ? (
              <CalendarCell
                cell={cell}
                slot={slot}
                isSel={isSel}
                onSelect={onSelect}
                allowOccupied={allowOccupied}
                alignRight={alignRight}
              />
            ) : slot ? (
              <button
                disabled={!free}
                title={free ? "Disponível para agendamento" : "Indisponível"}
                onClick={() => free && onSelect(slot.start)}
                className={[
                  "w-full h-full rounded transition-all duration-150 relative overflow-hidden",
                  isSel
                    ? "bg-brand text-white border border-brand-dark shadow-[0_0_12px_rgba(88,101,242,0.4)]"
                    : free
                    ? "bg-emerald-500/10 hover:bg-emerald-500/25 border border-emerald-500/15 hover:border-emerald-500/30 text-emerald-400 shadow-[inset_0_1px_1px_rgba(255,255,255,0.02)] hover:scale-[1.02] active:scale-[0.98]"
                    : "bg-transparent cursor-not-allowed border border-transparent",
                ].join(" ")}
              />
            ) : null}
          </div>
        );
      })}
    </>
  );
}

function CalendarCell({
  cell,
  slot,
  isSel,
  onSelect,
  allowOccupied,
  alignRight,
}: {
  cell: CellParty;
  slot: Slot | undefined;
  isSel: boolean;
  onSelect: (iso: string) => void;
  allowOccupied: boolean;
  alignRight: boolean;
}) {
  const { party, isStart } = cell;

  const handleOverwrite = () => {
    if (
      slot &&
      window.confirm(
        `Esse horário já tem uma PT (${party.members.map((m) => m.nick).join(", ") || party.difficulty}). Marcar mesmo assim?`
      )
    ) {
      onSelect(slot.start);
    }
  };

  const styleClass = [
    "w-full h-full rounded text-[10px] leading-tight px-2 py-0.5 overflow-hidden flex flex-col justify-center text-left border relative transition-all duration-150",
    isSel
      ? "bg-brand border-brand-dark shadow-[0_0_12px_rgba(88,101,242,0.4)]"
      : party.difficulty === "HARD"
      ? "bg-red-500/10 hover:bg-red-500/20 border-red-500/20 hover:border-red-500/35 text-red-200"
      : "bg-purple-500/10 hover:bg-purple-500/20 border-purple-500/20 hover:border-purple-500/35 text-purple-200",
    allowOccupied && isStart ? "hover:scale-[1.02] active:scale-[0.98] cursor-pointer" : "cursor-help",
  ].join(" ");

  const content = isStart ? (
    <div className="flex flex-col h-full justify-between">
      <div className="flex items-center justify-between">
        <span className="font-extrabold uppercase tracking-wide text-[9px] opacity-90">
          💀 {party.difficulty}
        </span>
        <span className="text-[8px] opacity-60">Fixo</span>
      </div>
      <span className="truncate font-medium text-gray-300 text-[9px]">
        {party.members.map((m) => m.nick).join(", ") || "Sem membros"}
      </span>
    </div>
  ) : (
    <div className="flex items-center gap-1.5 h-full opacity-60 overflow-hidden select-none">
      <div className="flex gap-1 items-center truncate text-[9px]">
        {party.members.map((m, idx) => {
          let roleShort = "T";
          if (m.role === "DPS") roleShort = "D";
          else if (m.role === "SUP") roleShort = "S";
          return (
            <span key={idx} className="truncate">
              {roleShort}·{m.nick}
            </span>
          );
        })}
      </div>
    </div>
  );

  return (
    <>
      {allowOccupied && isStart && slot ? (
        <button onClick={handleOverwrite} className={styleClass}>
          {content}
        </button>
      ) : (
        <div className={styleClass}>{content}</div>
      )}

      {/* Popover flutuante para mostrar membros ricos no hover */}
      <PartyPopover party={party} alignRight={alignRight} />
    </>
  );
}

function PartyPopover({ party, alignRight }: { party: CalendarParty; alignRight: boolean }) {
  return (
    <div
      className={[
        "absolute z-50 hidden group-hover:flex flex-col bg-gray-950/95 backdrop-blur-md border border-gray-850 rounded-xl shadow-2xl p-4 w-72 pointer-events-none text-left bottom-full mb-2.5 transition-all duration-200",
        alignRight ? "right-0" : "left-0",
      ].join(" ")}
    >
      {/* Cabeçalho Popover */}
      <div className="flex items-center justify-between border-b border-gray-800/70 pb-2.5 mb-2.5">
        <span
          className={[
            "text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded border shadow-sm",
            party.difficulty === "HARD"
              ? "bg-red-500/10 text-red-400 border-red-500/25 shadow-[0_0_8px_rgba(239,68,68,0.1)]"
              : "bg-purple-500/10 text-purple-400 border-purple-500/25 shadow-[0_0_8px_rgba(168,85,247,0.1)]",
          ].join(" ")}
        >
          PT {party.difficulty}
        </span>
        <span className="text-[10px] text-gray-500 font-semibold tabular-nums">
          Início: {String(party.hour).padStart(2, "0")}:00
        </span>
      </div>

      {/* Membros */}
      <div className="space-y-2 max-h-60 overflow-y-auto pr-0.5">
        {party.members.map((m, idx) => {
          let roleColor = "text-cyan-400 bg-cyan-950/45 border-cyan-800/40 shadow-[0_0_6px_rgba(6,182,212,0.1)]";
          let roleLabel = "TANK";
          if (m.role === "DPS") {
            roleColor = "text-rose-400 bg-rose-950/45 border-rose-800/40 shadow-[0_0_6px_rgba(244,63,94,0.1)]";
            roleLabel = "DPS";
          } else if (m.role === "SUP") {
            roleColor = "text-emerald-400 bg-emerald-950/45 border-emerald-800/40 shadow-[0_0_6px_rgba(16,185,129,0.1)]";
            roleLabel = "SUP";
          }

          return (
            <div
              key={idx}
              className="flex items-center justify-between text-xs py-1.5 px-2 rounded-lg bg-gray-900/40 border border-gray-800/50 hover:bg-gray-900/80 transition-colors"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className={`text-[8px] font-extrabold uppercase px-1.5 py-0.5 rounded border shrink-0 ${roleColor}`}>
                  {roleLabel}
                </span>
                <div className="truncate">
                  <span className="font-bold text-gray-200 block truncate">{m.nick}</span>
                  {m.character && (
                    <span className="text-[9px] text-gray-400 block truncate italic">
                      {m.character}
                    </span>
                  )}
                </div>
              </div>
              
              <div className="flex items-center gap-1.5 shrink-0 ml-2">
                {m.is_coleader && (
                  <span title="Co-líder da PT" className="text-xs">👑</span>
                )}
                {m.is_external && (
                  <span className="text-[8px] text-gray-500 bg-gray-900 border border-gray-800 px-1 py-0.5 rounded uppercase font-bold">Ext</span>
                )}
                <span
                  className={[
                    "text-[9px] px-1.5 py-0.5 rounded-full font-bold uppercase tracking-wider border",
                    m.confirmed
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20 shadow-[0_0_6px_rgba(16,185,129,0.05)]"
                      : "bg-amber-500/10 text-amber-400 border-amber-500/20 shadow-[0_0_6px_rgba(245,158,11,0.05)]",
                  ].join(" ")}
                >
                  {m.confirmed ? "Confirmado" : "Pendente"}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

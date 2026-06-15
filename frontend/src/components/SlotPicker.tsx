import {
  CalendarParty, WEEKDAY_LABEL, WEEKDAY_SHORT, DURATION_OPTIONS,
  fmtTime, fmtDuration, SLOT_STEP_MIN,
} from "../lib/api";

export interface SlotValue {
  weekday: number;     // 0=Seg .. 6=Dom
  time: string;        // "HH:MM"
  durationMin: number;
}

interface Props {
  value: SlotValue;
  onChange: (v: SlotValue) => void;
  parties?: CalendarParty[];   // PTs existentes (ocupação + "começar após")
  excludeScheduleId?: number;  // ao remarcar, ignora a própria PT
}

function partyStartMin(p: CalendarParty) {
  return p.hour * 60 + (p.minute ?? 0);
}
function partyEndMin(p: CalendarParty) {
  return partyStartMin(p) + (p.duration_minutes ?? 180);
}

export default function SlotPicker({ value, onChange, parties = [], excludeScheduleId }: Props) {
  const others = parties.filter((p) => p.schedule_id !== excludeScheduleId);

  const [h, m] = value.time.split(":").map(Number);
  const startMin = h * 60 + m;
  const endMin = startMin + value.durationMin;
  const endWeekday = (value.weekday + Math.floor(endMin / 1440)) % 7;

  // PTs no dia escolhido (dica de ocupação)
  const sameDay = others
    .filter((p) => p.weekday === value.weekday)
    .sort((a, b) => partyStartMin(a) - partyStartMin(b));

  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-3 gap-3">
        {/* Dia */}
        <label className="block">
          <span className="block text-xs text-gray-400 mb-1">Dia da semana</span>
          <select
            className="w-full bg-gray-800 rounded px-3 py-2 text-sm"
            value={value.weekday}
            onChange={(e) => onChange({ ...value, weekday: Number(e.target.value) })}
          >
            {WEEKDAY_LABEL.map((d, i) => <option key={i} value={i}>{d}</option>)}
          </select>
        </label>

        {/* Início */}
        <label className="block">
          <span className="block text-xs text-gray-400 mb-1">Início</span>
          <input
            type="time"
            step={SLOT_STEP_MIN * 60}
            value={value.time}
            onChange={(e) => onChange({ ...value, time: e.target.value || "20:00" })}
            className="w-full bg-gray-800 rounded px-3 py-2 text-sm"
          />
        </label>

        {/* Duração */}
        <label className="block">
          <span className="block text-xs text-gray-400 mb-1">Duração</span>
          <select
            className="w-full bg-gray-800 rounded px-3 py-2 text-sm"
            value={value.durationMin}
            onChange={(e) => onChange({ ...value, durationMin: Number(e.target.value) })}
          >
            {DURATION_OPTIONS.map((min) => <option key={min} value={min}>{fmtDuration(min)}</option>)}
          </select>
        </label>
      </div>

      <p className="text-sm text-gray-400">
        <strong className="text-brand">{WEEKDAY_LABEL[value.weekday]}</strong>{" "}
        {value.time} → {fmtTime(endMin)}
        {endWeekday !== value.weekday && <span className="text-gray-500"> ({WEEKDAY_SHORT[endWeekday]})</span>}{" "}
        <span className="text-gray-500">· {fmtDuration(value.durationMin)}</span>
      </p>

      {/* Começar logo após outra PT */}
      {others.length > 0 && (
        <label className="block">
          <span className="block text-xs text-gray-400 mb-1">Começar logo após outra PT (opcional)</span>
          <select
            className="w-full bg-gray-800 rounded px-3 py-2 text-sm"
            value=""
            onChange={(e) => {
              const p = others.find((x) => String(x.schedule_id) === e.target.value);
              if (!p) return;
              const e2 = partyEndMin(p);
              onChange({ ...value, weekday: (p.weekday + Math.floor(e2 / 1440)) % 7, time: fmtTime(e2) });
            }}
          >
            <option value="">Escolher uma PT...</option>
            {others.map((p) => (
              <option key={p.schedule_id} value={p.schedule_id}>
                {WEEKDAY_SHORT[p.weekday]} {fmtTime(partyStartMin(p))}–{fmtTime(partyEndMin(p))} {p.difficulty} → começa {fmtTime(partyEndMin(p))}
              </option>
            ))}
          </select>
        </label>
      )}

      {/* Ocupação do dia */}
      <div className="text-xs text-gray-500">
        {sameDay.length === 0 ? (
          <span>Nenhuma PT em {WEEKDAY_LABEL[value.weekday]}.</span>
        ) : (
          <span>
            PTs em {WEEKDAY_LABEL[value.weekday]}:{" "}
            {sameDay.map((p) => `${fmtTime(partyStartMin(p))}–${fmtTime(partyEndMin(p) % 1440)} ${p.difficulty}`).join(" · ")}
          </span>
        )}
      </div>
    </div>
  );
}

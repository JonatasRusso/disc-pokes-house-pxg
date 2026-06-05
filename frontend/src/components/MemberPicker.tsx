import { Member } from "../lib/api";

export interface PartyMemberInput {
  discord_id: string;
  role: string;
  character_id: number | null;
}

const ROLES = ["DPS", "SUP", "TANK"] as const;

interface Props {
  members: Member[];          // todos os membros do servidor
  excludeId: string;          // discord_id do criador (não selecionável)
  value: PartyMemberInput[];  // 3 slots
  onChange: (next: PartyMemberInput[]) => void;
}

export default function MemberPicker({ members, excludeId, value, onChange }: Props) {
  const update = (i: number, patch: Partial<PartyMemberInput>) =>
    onChange(value.map((m, idx) => (idx === i ? { ...m, ...patch } : m)));

  // IDs já escolhidos em outros slots (para não repetir)
  const chosen = new Set(value.map((m) => m.discord_id).filter(Boolean));

  return (
    <div className="space-y-3">
      {value.map((row, i) => {
        const selected = members.find((m) => m.discord_id === row.discord_id);
        const noChar   = selected && selected.characters.length === 0;
        return (
          <div key={i} className="bg-gray-800 rounded-lg p-3 space-y-2">
            <div className="flex gap-2">
              {/* Membro */}
              <select
                className="bg-gray-900 rounded px-2 py-2 text-sm flex-1"
                value={row.discord_id}
                onChange={(e) => update(i, { discord_id: e.target.value, character_id: null })}
              >
                <option value="">Membro {i + 2}...</option>
                {members
                  .filter((m) => m.discord_id !== excludeId && (!chosen.has(m.discord_id) || m.discord_id === row.discord_id))
                  .map((m) => (
                    <option key={m.discord_id} value={m.discord_id}>{m.username}</option>
                  ))}
              </select>

              {/* Função */}
              <select
                className="bg-gray-900 rounded px-2 py-2 text-sm"
                value={row.role}
                onChange={(e) => update(i, { role: e.target.value })}
              >
                {ROLES.map((r) => <option key={r}>{r}</option>)}
              </select>
            </div>

            {/* Personagem do membro selecionado */}
            {selected && !noChar && (
              <select
                className="w-full bg-gray-900 rounded px-2 py-2 text-sm"
                value={row.character_id ?? ""}
                onChange={(e) => update(i, { character_id: e.target.value ? Number(e.target.value) : null })}
              >
                <option value="">Selecione o personagem...</option>
                {selected.characters.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            )}

            {noChar && (
              <p className="text-xs text-yellow-400">
                ⚠️ Sem personagem livre — será convidado(a) no Discord para criar um.
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

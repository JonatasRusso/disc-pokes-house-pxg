import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getCharacters, createCharacter, updateCharacter, deleteCharacter, updateMySettings, Character } from "../lib/api";
import { useAuth } from "../lib/useAuth";

export default function Perfil() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data: chars = [], isLoading } = useQuery({ queryKey: ["characters"], queryFn: getCharacters });

  const [newName, setNewName] = useState("");
  const [editing, setEditing] = useState<Character | null>(null);
  const [lead, setLead] = useState<number>(user?.notify_lead_minutes ?? 30);
  useEffect(() => {
    if (user?.notify_lead_minutes) setLead(user.notify_lead_minutes);
  }, [user?.notify_lead_minutes]);

  const saveLead = useMutation({
    mutationFn: () => updateMySettings(lead),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });

  const create = useMutation({
    mutationFn: () => createCharacter({ name: newName }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["characters"] }); setNewName(""); },
  });

  const update = useMutation({
    mutationFn: (c: Character) => updateCharacter(c.id, { name: c.name }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["characters"] }); setEditing(null); },
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteCharacter(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["characters"] }),
  });

  return (
    <div className="max-w-lg space-y-6">
      <h1 className="text-2xl font-bold">Perfil</h1>

      {/* Info Discord */}
      <div className="bg-gray-900 rounded-lg p-4 flex items-center gap-4">
        {user?.avatar_url && <img src={user.avatar_url} className="w-12 h-12 rounded-full" alt="" />}
        <div>
          <p className="font-semibold">{user?.username}</p>
          <p className="text-gray-500 text-sm">ID: {user?.discord_id}</p>
          {user?.is_admin && <span className="text-xs bg-brand px-2 py-0.5 rounded-full">Admin</span>}
        </div>
      </div>

      {/* Notificações */}
      <section className="bg-gray-900 rounded-lg p-4">
        <h2 className="text-lg font-semibold mb-1">🔔 Notificações de PT</h2>
        <p className="text-gray-500 text-xs mb-3">
          Quanto tempo antes da PT você quer o <strong>primeiro</strong> aviso no Discord.
          (Os avisos de 1 min, 30s e de atraso são automáticos.)
        </p>
        <div className="flex items-center gap-2">
          <input
            type="number" min={1} max={1440}
            className="bg-gray-800 rounded px-3 py-2 text-sm w-24"
            value={lead}
            onChange={(e) => setLead(Number(e.target.value))}
          />
          <span className="text-sm text-gray-400">minutos antes</span>
          <button
            onClick={() => saveLead.mutate()}
            disabled={saveLead.isPending}
            className="ml-auto bg-brand hover:bg-brand-dark disabled:opacity-40 text-white text-sm px-4 py-2 rounded"
          >
            {saveLead.isPending ? "Salvando..." : saveLead.isSuccess ? "Salvo ✓" : "Salvar"}
          </button>
        </div>
      </section>

      {/* Personagens */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Meus Personagens</h2>
        {isLoading ? (
          <p className="text-gray-500 text-sm">Carregando...</p>
        ) : chars.length === 0 ? (
          <p className="text-gray-500 text-sm">Nenhum personagem cadastrado ainda.</p>
        ) : (
          <ul className="space-y-2 mb-4">
            {chars.map((c) => (
              <li key={c.id} className="bg-gray-900 rounded-lg px-4 py-3 flex items-center gap-3">
                {editing?.id === c.id ? (
                  <>
                    <input
                      className="bg-gray-800 rounded px-2 py-1 text-sm flex-1"
                      value={editing.name}
                      onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                    />
                    <button onClick={() => update.mutate(editing)} className="text-green-400 text-sm hover:underline">Salvar</button>
                    <button onClick={() => setEditing(null)} className="text-gray-500 text-sm hover:underline">Cancelar</button>
                  </>
                ) : (
                  <>
                    <span className="flex-1 font-medium">{c.name}</span>
                    <button onClick={() => setEditing(c)} className="text-brand text-sm hover:underline">Editar</button>
                    <button onClick={() => remove.mutate(c.id)} className="text-red-500 text-sm hover:underline">Excluir</button>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}

        {/* Novo personagem */}
        <div className="bg-gray-900 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-semibold text-gray-400">Adicionar personagem</h3>
          <div className="flex gap-2">
            <input
              className="bg-gray-800 rounded px-3 py-2 text-sm flex-1"
              placeholder="Nome do personagem"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && newName.trim()) create.mutate(); }}
            />
            <button
              onClick={() => create.mutate()}
              disabled={!newName.trim() || create.isPending}
              className="bg-brand hover:bg-brand-dark disabled:opacity-40 text-white px-4 py-2 rounded text-sm font-medium"
            >
              Adicionar
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

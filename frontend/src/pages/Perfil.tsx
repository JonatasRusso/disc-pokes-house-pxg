import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getCharacters, createCharacter, updateCharacter, deleteCharacter, Character } from "../lib/api";
import { useAuth } from "../lib/useAuth";

export default function Perfil() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data: chars = [], isLoading } = useQuery({ queryKey: ["characters"], queryFn: getCharacters });

  const [newName, setNewName]   = useState("");
  const [newCls,  setNewCls]   = useState("");
  const [editing, setEditing]  = useState<Character | null>(null);

  const create = useMutation({
    mutationFn: () => createCharacter({ name: newName, cls: newCls || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["characters"] }); setNewName(""); setNewCls(""); },
  });

  const update = useMutation({
    mutationFn: (c: Character) => updateCharacter(c.id, { name: c.name, cls: c.class ?? undefined }),
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
                    <input
                      className="bg-gray-800 rounded px-2 py-1 text-sm w-28"
                      value={editing.class ?? ""}
                      placeholder="Classe"
                      onChange={(e) => setEditing({ ...editing, class: e.target.value })}
                    />
                    <button onClick={() => update.mutate(editing)} className="text-green-400 text-sm hover:underline">Salvar</button>
                    <button onClick={() => setEditing(null)} className="text-gray-500 text-sm hover:underline">Cancelar</button>
                  </>
                ) : (
                  <>
                    <span className="flex-1 font-medium">{c.name}</span>
                    {c.class && <span className="text-gray-500 text-sm">{c.class}</span>}
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
            />
            <input
              className="bg-gray-800 rounded px-3 py-2 text-sm w-32"
              placeholder="Classe"
              value={newCls}
              onChange={(e) => setNewCls(e.target.value)}
            />
            <button
              onClick={() => create.mutate()}
              disabled={!newName.trim()}
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

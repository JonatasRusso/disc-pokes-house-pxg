import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getPokemon, createPokemon, updatePokemon, deletePokemon, unassignPokemon, Pokemon } from "../lib/api";

const CATEGORIES = ["A", "B", "C"] as const;
const CATEGORY_LABEL: Record<string, string> = {
  A: "Tank",
  B: "DPS",
  C: "Sup",
};

export default function AdminPokemon() {
  const qc = useQueryClient();
  const { data: pokemon = [], isLoading } = useQuery({ queryKey: ["pokemon"], queryFn: getPokemon });

  const [name, setName]       = useState("");
  const [imageUrl, setImage]  = useState("");
  const [category, setCat]    = useState<string>("A");
  const [error, setError]     = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);

  const refresh = () => qc.invalidateQueries({ queryKey: ["pokemon"] });

  const create = useMutation({
    mutationFn: () => createPokemon({ name, image_url: imageUrl || undefined, category }),
    onSuccess: () => { refresh(); setName(""); setImage(""); },
    onError: (e: Error) => setError(e.message),
  });

  const update = useMutation({
    mutationFn: (vars: { id: number; name: string; image_url: string; category: string }) =>
      updatePokemon(vars.id, { name: vars.name, image_url: vars.image_url, category: vars.category }),
    onSuccess: () => { refresh(); setEditingId(null); },
    onError: (e: Error) => setError(e.message),
  });

  const remove = useMutation({
    mutationFn: deletePokemon,
    onSuccess: refresh,
  });

  const unassign = useMutation({
    mutationFn: unassignPokemon,
    onSuccess: refresh,
  });

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Admin — Pokémons</h1>

      <p className="text-sm text-gray-400 bg-gray-800/50 rounded px-3 py-2">
        💡 Depois de cadastrar, poste o painel no Discord com um destes comandos:
        <code className="text-brand"> /pokemon-painel</code> (imagens grandes, marca com 🎯) ou
        <code className="text-brand"> /pokemon-botoes</code> (grade com botões). Teste os dois e use o que preferir.
      </p>

      {/* Form de adição */}
      <section className="bg-gray-900 rounded-lg p-5 space-y-4 max-w-lg">
        <h2 className="text-lg font-semibold">Adicionar pokémon</h2>
        {error && <p className="text-red-400 text-sm bg-red-900/30 px-3 py-2 rounded">{error}</p>}
        <div className="space-y-3">
          <input
            className="w-full bg-gray-800 rounded px-3 py-2 text-sm"
            placeholder="Nome do pokémon"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            className="w-full bg-gray-800 rounded px-3 py-2 text-sm"
            placeholder="URL da imagem (opcional)"
            value={imageUrl}
            onChange={(e) => setImage(e.target.value)}
          />
          <div className="flex gap-2">
            {CATEGORIES.map((c) => (
              <button
                key={c}
                onClick={() => setCat(c)}
                className={`flex-1 py-2 rounded text-sm font-medium transition-colors ${category === c ? "bg-brand text-white" : "bg-gray-800 text-gray-300 hover:bg-gray-700"}`}
              >
                {CATEGORY_LABEL[c]}
              </button>
            ))}
          </div>
          <button
            onClick={() => create.mutate()}
            disabled={!name.trim() || create.isPending}
            className="w-full bg-brand hover:bg-brand-dark disabled:opacity-40 text-white font-semibold py-2 rounded transition-colors"
          >
            {create.isPending ? "Adicionando..." : "Adicionar"}
          </button>
        </div>
      </section>

      {/* Lista por categoria */}
      {isLoading ? (
        <p className="text-gray-500">Carregando...</p>
      ) : (
        CATEGORIES.map((cat) => {
          const group = pokemon.filter((p) => p.category === cat);
          if (!group.length) return null;
          return (
            <section key={cat}>
              <h2 className="text-lg font-semibold mb-3">
                {CATEGORY_LABEL[cat]}{" "}
                <span className="text-gray-500 text-sm font-normal">({group.length})</span>
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                {group.map((p) => (
                  <PokemonCard
                    key={`${p.id}-${editingId === p.id ? "edit" : "view"}`}
                    pokemon={p}
                    editing={editingId === p.id}
                    onEdit={() => setEditingId(p.id)}
                    onCancel={() => setEditingId(null)}
                    onSave={(vars) => update.mutate({ id: p.id, ...vars })}
                    onDelete={() => { if (confirm(`Excluir ${p.name}?`)) remove.mutate(p.id); }}
                    onUnassign={() => unassign.mutate(p.id)}
                  />
                ))}
              </div>
            </section>
          );
        })
      )}
    </div>
  );
}

function PokemonCard({
  pokemon: p, editing, onEdit, onCancel, onSave, onDelete, onUnassign,
}: {
  pokemon: Pokemon;
  editing: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onSave: (vars: { name: string; image_url: string; category: string }) => void;
  onDelete: () => void;
  onUnassign: () => void;
}) {
  const [name, setName] = useState(p.name);
  const [img, setImg]   = useState(p.image_url ?? "");
  const [cat, setCat]   = useState<string>(p.category);

  if (editing) {
    return (
      <div className="bg-gray-900 rounded-lg p-3 flex flex-col gap-2 border border-brand">
        <input
          className="bg-gray-800 rounded px-2 py-1 text-sm"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Nome"
        />
        <input
          className="bg-gray-800 rounded px-2 py-1 text-xs"
          value={img}
          onChange={(e) => setImg(e.target.value)}
          placeholder="URL da imagem"
        />
        <div className="flex gap-1">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              onClick={() => setCat(c)}
              className={`flex-1 py-1 rounded text-xs ${cat === c ? "bg-brand text-white" : "bg-gray-800 text-gray-300"}`}
            >
              {CATEGORY_LABEL[c]}
            </button>
          ))}
        </div>
        <div className="flex justify-between text-xs">
          <button onClick={() => onSave({ name, image_url: img, category: cat })} className="text-green-400 hover:underline">Salvar</button>
          <button onClick={onCancel} className="text-gray-500 hover:underline">Cancelar</button>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-gray-900 rounded-lg p-3 flex flex-col gap-2 border ${p.assigned_to ? "border-green-700" : "border-gray-800"}`}>
      {p.image_url ? (
        <img src={p.image_url} alt={p.name} className="w-full h-20 object-contain rounded" />
      ) : (
        <div className="w-full h-20 bg-gray-800 rounded flex items-center justify-center text-3xl">🎮</div>
      )}
      <p className="font-medium text-sm text-center">{p.name}</p>
      <div className="text-center text-xs">
        {p.assigned_to ? (
          <>
            <p className="text-green-400 mb-1">Em uso</p>
            <button onClick={onUnassign} className="text-red-400 hover:underline">Liberar</button>
          </>
        ) : (
          <p className="text-gray-500">Livre</p>
        )}
      </div>
      <div className="flex justify-between text-xs pt-1 border-t border-gray-800">
        <button onClick={onEdit} className="text-brand hover:underline">Editar</button>
        <button onClick={onDelete} className="text-red-500 hover:underline">Excluir</button>
      </div>
    </div>
  );
}

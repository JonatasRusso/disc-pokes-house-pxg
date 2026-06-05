import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getPokemon, createPokemon, unassignPokemon, Pokemon } from "../lib/api";

const CATEGORIES = ["A", "B", "C"] as const;
const CATEGORY_LABEL: Record<string, string> = {
  A: "Categoria A",
  B: "Categoria B",
  C: "Categoria C",
};

export default function AdminPokemon() {
  const qc = useQueryClient();
  const { data: pokemon = [], isLoading } = useQuery({ queryKey: ["pokemon"], queryFn: getPokemon });

  const [name, setName]       = useState("");
  const [imageUrl, setImage]  = useState("");
  const [category, setCat]    = useState<string>("A");
  const [error, setError]     = useState("");

  const create = useMutation({
    mutationFn: () => createPokemon({ name, image_url: imageUrl || undefined, category }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pokemon"] });
      setName(""); setImage("");
    },
    onError: (e: Error) => setError(e.message),
  });

  const unassign = useMutation({
    mutationFn: unassignPokemon,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pokemon"] }),
  });

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Admin — Pokémons</h1>

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
                  <PokemonCard key={p.id} pokemon={p} onUnassign={() => unassign.mutate(p.id)} />
                ))}
              </div>
            </section>
          );
        })
      )}
    </div>
  );
}

function PokemonCard({ pokemon: p, onUnassign }: { pokemon: Pokemon; onUnassign: () => void }) {
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
    </div>
  );
}

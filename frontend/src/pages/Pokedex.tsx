import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getPokemon, assignPokemon, unassignPokemon, Pokemon } from "../lib/api";
import { useAuth } from "../lib/useAuth";

const CATEGORY_LABEL: Record<string, string> = {
  A: "Categoria A",
  B: "Categoria B",
  C: "Categoria C",
};

export default function Pokedex() {
  const { user } = useAuth();
  const qc       = useQueryClient();
  const { data: pokemon = [], isLoading } = useQuery({ queryKey: ["pokemon"], queryFn: getPokemon });

  const assign   = useMutation({ mutationFn: assignPokemon,   onSuccess: () => qc.invalidateQueries({ queryKey: ["pokemon"] }) });
  const unassign = useMutation({ mutationFn: unassignPokemon, onSuccess: () => qc.invalidateQueries({ queryKey: ["pokemon"] }) });

  if (isLoading) return <p className="text-gray-500">Carregando...</p>;

  const categories = ["A", "B", "C"] as const;

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Pokédex do Servidor</h1>

      {categories.map((cat) => {
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
                  key={p.id}
                  pokemon={p}
                  myId={user?.discord_id ?? ""}
                  onAssign={() => assign.mutate(p.id)}
                  onUnassign={() => unassign.mutate(p.id)}
                />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function PokemonCard({
  pokemon: p, myId, onAssign, onUnassign,
}: {
  pokemon: Pokemon;
  myId: string;
  onAssign: () => void;
  onUnassign: () => void;
}) {
  const isMine   = p.assigned_to === myId;
  const isTaken  = !!p.assigned_to && !isMine;

  return (
    <div className={`bg-gray-900 rounded-lg p-3 flex flex-col gap-2 border ${
      isMine ? "border-green-600" : isTaken ? "border-gray-700" : "border-gray-800"
    }`}>
      {p.image_url ? (
        <img src={p.image_url} alt={p.name} className="w-full h-20 object-contain rounded" />
      ) : (
        <div className="w-full h-20 bg-gray-800 rounded flex items-center justify-center text-3xl">🎮</div>
      )}
      <p className="font-medium text-sm text-center">{p.name}</p>
      <div className="text-center">
        {isMine ? (
          <>
            <p className="text-green-400 text-xs mb-1">Você está usando</p>
            <button onClick={onUnassign} className="text-xs text-red-400 hover:underline">Liberar</button>
          </>
        ) : isTaken ? (
          <p className="text-gray-500 text-xs">Em uso</p>
        ) : (
          <button
            onClick={onAssign}
            className="w-full bg-brand hover:bg-brand-dark text-white text-xs py-1 rounded transition-colors"
          >
            Usar
          </button>
        )}
      </div>
    </div>
  );
}

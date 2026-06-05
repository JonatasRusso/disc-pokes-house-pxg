import { useQuery } from "@tanstack/react-query";
import { getSchedules, getPokemon, getHistory } from "../lib/api";
import { useAuth } from "../lib/useAuth";
import { Link } from "react-router-dom";

const STATUS_COLOR: Record<string, string> = {
  pending:     "bg-yellow-600",
  confirmed:   "bg-green-600",
  rescheduled: "bg-blue-600",
  missed:      "bg-red-700",
  cancelled:   "bg-gray-600",
};

export default function Dashboard() {
  const { user } = useAuth();
  const { data: schedules = [] } = useQuery({ queryKey: ["schedules"], queryFn: getSchedules });
  const { data: pokemon   = [] } = useQuery({ queryKey: ["pokemon"],   queryFn: getPokemon });

  const upcoming = schedules
    .filter((s) => ["pending", "confirmed"].includes(s.status))
    .slice(0, 3);

  const myPokemon = pokemon.filter((p) => p.assigned_to === user?.discord_id).slice(0, 6);
  const freePokemon = pokemon.filter((p) => !p.assigned_to).length;

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Olá, {user?.username} 👋</h1>

      {/* Próximos horários */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Próximos Horários</h2>
          <Link to="/agendar" className="text-sm text-brand hover:underline">+ Agendar</Link>
        </div>
        {upcoming.length === 0 ? (
          <p className="text-gray-500 text-sm">Nenhum horário agendado.</p>
        ) : (
          <div className="grid gap-3">
            {upcoming.map((s) => (
              <div key={s.id} className="bg-gray-900 rounded-lg p-4 flex items-center gap-4">
                <span className={`text-xs px-2 py-0.5 rounded-full text-white font-medium ${STATUS_COLOR[s.status]}`}>
                  {s.status}
                </span>
                <div>
                  <p className="font-medium">{s.difficulty}</p>
                  <p className="text-gray-400 text-sm">
                    {new Date(s.start_time).toLocaleString("pt-BR")} → {new Date(s.end_time).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                  </p>
                </div>
                <Link to={`/remarcar/${s.id}`} className="ml-auto text-sm text-gray-500 hover:text-orange-400 transition-colors">
                  Remarcar
                </Link>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Resumo pokémons */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Seus Pokémons em Uso</h2>
          {user?.is_admin && (
            <Link to="/admin/pokemon" className="text-sm text-brand hover:underline">Gerenciar</Link>
          )}
        </div>
        <div className="flex items-center gap-4 text-sm text-gray-400 mb-3">
          <span>🟢 {myPokemon.length} em uso por você</span>
          <span>⚪ {freePokemon} livres no servidor</span>
        </div>
        {myPokemon.length === 0 ? (
          <p className="text-gray-500 text-sm">Você não está usando nenhum pokémon.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {myPokemon.map((p) => (
              <span key={p.id} className="bg-gray-800 px-3 py-1 rounded-full text-sm">
                {p.name} <span className="text-gray-500 text-xs">[{p.category}]</span>
              </span>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

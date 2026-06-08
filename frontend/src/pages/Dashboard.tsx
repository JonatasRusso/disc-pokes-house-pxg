import { useQuery } from "@tanstack/react-query";
import { getSchedules, getPokemon, WEEKDAY_LABEL } from "../lib/api";
import { useAuth } from "../lib/useAuth";
import { Link } from "react-router-dom";

const STATUS_COLOR: Record<string, string> = {
  pending: "bg-yellow-600", confirmed: "bg-green-600", rescheduled: "bg-blue-600",
  missed: "bg-red-700", cancelled: "bg-gray-600",
};
const POKE_CATEGORY: Record<string, string> = { A: "Tank", B: "DPS", C: "Sup" };

export default function Dashboard() {
  const { user } = useAuth();
  const { data: schedules = [] } = useQuery({ queryKey: ["schedules"], queryFn: getSchedules });
  const { data: pokemon   = [] } = useQuery({ queryKey: ["pokemon"],   queryFn: getPokemon });

  const upcoming = schedules
    .filter((s) => s.status !== "cancelled" && s.status !== "missed")
    .slice(0, 5);

  const myPokemon = pokemon.filter((p) => p.assigned_to === user?.discord_id).slice(0, 6);
  const freePokemon = pokemon.filter((p) => !p.assigned_to).length;

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Olá, {user?.username} 👋</h1>

      {/* Resumo das PTs */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">💀 Suas PTs</h2>
          <Link to="/minhas-pts" className="text-sm text-brand hover:underline">Gerenciar →</Link>
        </div>
        {upcoming.length === 0 ? (
          <p className="text-gray-500 text-sm">
            Nenhuma PT agendada. <Link to="/agendar" className="text-brand hover:underline">Agendar uma</Link>.
          </p>
        ) : (
          <div className="grid gap-2">
            {upcoming.map((s) => {
              const realMembers = s.members.filter((m) => !m.is_guest);  // convidados não confirmam
              const confirmed = realMembers.filter((m) => m.confirmed).length;
              return (
                <Link key={s.id} to="/minhas-pts" className="bg-gray-900 hover:bg-gray-800 transition-colors rounded-lg p-3 flex items-center gap-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full text-white font-medium ${STATUS_COLOR[s.status]}`}>{s.status}</span>
                  <span className="font-medium">{s.difficulty}</span>
                  <span className="text-gray-400 text-sm">
                    🔁 {WEEKDAY_LABEL[s.weekday]} {String(s.hour).padStart(2, "0")}:00
                  </span>
                  {s.is_override && (
                    <span className="text-amber-400 text-xs" title="Remarcada só esta semana">📌 esta semana</span>
                  )}
                  <span className="ml-auto text-xs text-gray-500">
                    {confirmed}/{realMembers.length} confirmados
                  </span>
                </Link>
              );
            })}
          </div>
        )}
      </section>

      {/* Resumo pokémons */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Seus Pokémons em Uso</h2>
          {user?.is_admin && <Link to="/admin/pokemon" className="text-sm text-brand hover:underline">Gerenciar</Link>}
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
                {p.name} <span className="text-gray-500 text-xs">[{POKE_CATEGORY[p.category]}]</span>
              </span>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/useAuth";

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, isLoggedIn } = useAuth();
  const navigate = useNavigate();

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all duration-200 border ${
      isActive
        ? "bg-brand/15 text-brand border-brand/40 shadow-[0_0_12px_rgba(88,101,242,0.15)]"
        : "text-gray-400 border-transparent hover:bg-gray-900/50 hover:text-gray-100 hover:border-gray-800/80"
    }`;

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    navigate("/");
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-950 text-gray-100">
      <nav className="bg-gray-950/80 backdrop-blur-md border-b border-gray-900 sticky top-0 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 flex items-center gap-4 h-16">
          <Link to="/" className="text-brand font-black text-xl tracking-tight mr-6 flex items-center gap-2 hover:scale-[1.02] transition-transform">
            <span className="text-2xl">💀</span>
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-brand to-purple-400">
              VKG House
            </span>
          </Link>
          {isLoggedIn && (
            <>
              <NavLink to="/dashboard" className={navClass}>Dashboard</NavLink>
              <NavLink to="/minhas-pts" className={navClass}>Minhas PTs</NavLink>
              <NavLink to="/agendar" className={navClass}>Agendar</NavLink>
              <NavLink to="/calendario" className={navClass}>Calendário</NavLink>
              <NavLink to="/perfil" className={navClass}>Perfil</NavLink>
              {user?.is_admin && (
                <>
                  <NavLink to="/admin/planilha" className={navClass}>Admin</NavLink>
                  <NavLink to="/admin/pokemon" className={navClass}>Pokémons</NavLink>
                  <NavLink to="/admin/logs" className={navClass}>Logs</NavLink>
                </>
              )}
              <div className="ml-auto flex items-center gap-3">
                {user?.avatar_url && (
                  <img src={user.avatar_url} className="w-8 h-8 rounded-full" alt="" />
                )}
                <span className="text-sm text-gray-400">{user?.username}</span>
                {user?.is_admin && (
                  <span className="text-[10px] font-bold uppercase tracking-wide bg-brand text-white px-2 py-0.5 rounded-full">
                    Admin
                  </span>
                )}
                <button
                  onClick={logout}
                  className="text-sm text-gray-500 hover:text-white transition-colors"
                >
                  Sair
                </button>
              </div>
            </>
          )}
        </div>
      </nav>
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">{children}</main>
      <footer className="border-t border-gray-800 py-2 px-4 text-center text-xs text-gray-600">
        VKG House v{__APP_VERSION__}
      </footer>
    </div>
  );
}

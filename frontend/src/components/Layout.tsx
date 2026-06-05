import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/useAuth";

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, isLoggedIn } = useAuth();
  const navigate = useNavigate();

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded-md text-sm font-medium transition-colors ${
      isActive ? "bg-brand text-white" : "text-gray-300 hover:bg-gray-800"
    }`;

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    navigate("/");
  }

  return (
    <div className="min-h-screen flex flex-col">
      <nav className="bg-gray-900 border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 flex items-center gap-4 h-14">
          <Link to="/" className="text-brand font-bold text-lg mr-4">
            VKG House
          </Link>
          {isLoggedIn && (
            <>
              <NavLink to="/dashboard" className={navClass}>Dashboard</NavLink>
              <NavLink to="/agendar" className={navClass}>Agendar</NavLink>
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

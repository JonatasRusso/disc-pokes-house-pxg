import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./lib/useAuth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import { Analytics } from "@vercel/analytics/react"
import Dashboard from "./pages/Dashboard";
import MinhasPTs from "./pages/MinhasPTs";
import Calendario from "./pages/Calendario";
import Agendar from "./pages/Agendar";
import Remarcar from "./pages/Remarcar";
import Perfil from "./pages/Perfil";
import AdminPlanilha from "./pages/AdminPlanilha";
import AdminPokemon from "./pages/AdminPokemon";
import AdminLogs from "./pages/AdminLogs";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isLoggedIn, isLoading } = useAuth();
  if (isLoading) return <div className="p-8 text-gray-400">Carregando...</div>;
  if (!isLoggedIn) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <div className="p-8 text-gray-400">Carregando...</div>;
  if (!user?.is_admin) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Layout>
      <Analytics/>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
        <Route path="/minhas-pts" element={<RequireAuth><MinhasPTs /></RequireAuth>} />
        <Route path="/calendario" element={<RequireAuth><Calendario /></RequireAuth>} />
        <Route path="/agendar" element={<RequireAuth><Agendar /></RequireAuth>} />
        <Route path="/remarcar/:id" element={<RequireAuth><Remarcar /></RequireAuth>} />
        <Route path="/perfil" element={<RequireAuth><Perfil /></RequireAuth>} />
        <Route path="/admin/planilha" element={<RequireAuth><RequireAdmin><AdminPlanilha /></RequireAdmin></RequireAuth>} />
        <Route path="/admin/pokemon" element={<RequireAuth><RequireAdmin><AdminPokemon /></RequireAdmin></RequireAuth>} />
        <Route path="/admin/logs" element={<RequireAuth><RequireAdmin><AdminLogs /></RequireAdmin></RequireAuth>} />
      </Routes>
    </Layout>
  );
}

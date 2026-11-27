// Fontes self-hosted (nada de CDN). Eixos opsz + wght; SOFT/WONK ficam no padrão 0.
import "@fontsource-variable/fraunces/opsz.css";
import "@fontsource-variable/literata/opsz.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/componentes.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Busca } from "./features/busca/Busca";
import { Inicio } from "./features/inicio/Inicio";
import { Onboarding } from "./features/onboarding/Onboarding";
import { ProdutoProvisorio } from "./features/produto/ProdutoProvisorio";
import { perfilSalvo } from "./perfil";

// Sem perfil, a primeira visita começa pelo onboarding.
function ComPerfil({ children }: { children: React.ReactElement }) {
  return perfilSalvo() ? children : <Navigate to="/onboarding" replace />;
}

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ComPerfil><Inicio /></ComPerfil>} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/busca" element={<Busca />} />
        <Route path="/produto/:id" element={<ProdutoProvisorio />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);

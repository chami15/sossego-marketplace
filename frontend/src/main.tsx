// Fontes self-hosted (nada de CDN). Eixos opsz + wght; SOFT/WONK ficam no padrão 0.
import "@fontsource-variable/fraunces/opsz.css";
import "@fontsource-variable/literata/opsz.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/componentes.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Pronto } from "./features/inicio/Pronto";
import { Onboarding } from "./features/onboarding/Onboarding";
import { perfilSalvo } from "./perfil";

function Inicio() {
  return perfilSalvo() ? <Pronto /> : <Navigate to="/onboarding" replace />;
}

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Inicio />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);

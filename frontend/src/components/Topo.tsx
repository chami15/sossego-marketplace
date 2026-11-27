import { Link } from "react-router-dom";

import { CampoBusca } from "./CampoBusca";

// Topo das telas internas: logo à esquerda e busca no centro, só isso (sem menu, sem barra lateral).
export function Topo({ busca = "" }: { busca?: string }) {
  return (
    <header className="topo">
      <div className="topo__dentro">
        <Link to="/" className="topo__marca">
          Sossego
        </Link>
        <div className="topo__busca">
          <CampoBusca key={busca} inicial={busca} />
        </div>
      </div>
    </header>
  );
}

export function Rodape() {
  return (
    <footer className="rodape">
      <p>Preços do histórico coletado pelo Sossego. Nenhuma busca vai às lojas.</p>
      <Link to="/onboarding">refazer preferências</Link>
    </footer>
  );
}

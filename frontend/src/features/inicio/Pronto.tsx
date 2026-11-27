import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, type Perfil } from "../../api/cliente";
import { perfilSalvo } from "../../perfil";
import "./pronto.css";

// Provisória: a página inicial com ofertas é a Fase 7. Aqui só confirma o que ficou salvo.
export function Pronto() {
  const [perfil, setPerfil] = useState<Perfil | null>(null);

  useEffect(() => {
    const id = perfilSalvo();
    if (id) api.perfil(id).then(setPerfil).catch(() => undefined);
  }, []);

  return (
    <div className="pronto">
      <main className="pronto__corpo">
        <p className="pronto__marca">Sossego</p>
        <h1 className="pronto__titulo">Pronto. Suas preferências estão salvas.</h1>
        {perfil && (
          <dl className="pronto__resumo">
            <dt>Categorias</dt>
            <dd>{perfil.categorias.join(", ") || "nenhuma"}</dd>
            <dt>Termos</dt>
            <dd>{perfil.interesses.join(", ") || "nenhum"}</dd>
            <dt>Lojas</dt>
            <dd>{perfil.lojas.join(", ") || "sem preferência"}</dd>
          </dl>
        )}
        <p className="pronto__nota">A página inicial com as ofertas chega na próxima etapa.</p>
      </main>
      <footer className="pronto__rodape">
        <Link to="/onboarding">refazer preferências</Link>
      </footer>
    </div>
  );
}

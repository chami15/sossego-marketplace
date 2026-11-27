import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, type Categoria, type Loja, type Perfil } from "../../api/cliente";
import { perfilSalvo } from "../../perfil";
import "./pronto.css";

// Provisória: a página inicial com ofertas é a Fase 7. Aqui só confirma o que ficou salvo.
export function Pronto() {
  const [dados, setDados] = useState<{ perfil: Perfil; categorias: Categoria[]; lojas: Loja[] } | null>(null);

  useEffect(() => {
    const id = perfilSalvo();
    if (!id) return;
    Promise.all([api.perfil(id), api.categorias(), api.lojas()])
      .then(([perfil, categorias, lojas]) => setDados({ perfil, categorias, lojas }))
      .catch(() => undefined);
  }, []);

  // Nome de exibição, nunca o slug ("jogos-tabuleiro" → "Jogos de tabuleiro").
  const nome = (lista: { slug: string; nome: string }[], slug: string) =>
    lista.find((x) => x.slug === slug)?.nome ?? slug;

  return (
    <div className="pronto">
      <main className="pronto__corpo">
        <p className="pronto__marca">Sossego</p>
        <h1 className="pronto__titulo">Pronto. Suas preferências estão salvas.</h1>
        {dados && (
          <dl className="pronto__resumo">
            <dt>Categorias</dt>
            <dd>{dados.perfil.categorias.map((s) => nome(dados.categorias, s)).join(", ") || "nenhuma"}</dd>
            <dt>Termos</dt>
            <dd>{dados.perfil.interesses.join(", ") || "nenhum"}</dd>
            <dt>Lojas</dt>
            <dd>{dados.perfil.lojas.map((s) => nome(dados.lojas, s)).join(", ") || "sem preferência"}</dd>
          </dl>
        )}
      </main>
      <footer className="pronto__rodape">
        <Link to="/onboarding">refazer preferências</Link>
      </footer>
    </div>
  );
}

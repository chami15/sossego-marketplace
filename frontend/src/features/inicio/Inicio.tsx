import { Link } from "react-router-dom";
import { useEffect, useState } from "react";

import { api, type Card, type Inicio as DadosInicio, type Recomendacao } from "../../api/cliente";
import { Aviso } from "../../components/Aviso";
import { CampoBusca } from "../../components/CampoBusca";
import { CardProduto } from "../../components/CardProduto";
import { IconeCategoria } from "../../components/IconeCategoria";
import { Rodape } from "../../components/Topo";
import { perfilSalvo } from "../../perfil";
import "./inicio.css";

type Estado = { tipo: "carregando" } | { tipo: "erro" } | { tipo: "ok"; dados: DadosInicio };

function Secao({ id, titulo, cards, vazio }: { id: string; titulo: string; cards: (Card | Recomendacao)[]; vazio?: string }) {
  if (!cards.length && !vazio) return null;
  return (
    <section className="secao" aria-labelledby={id}>
      <div className="secao__cabeca">
        <h2 id={id} className="secao__titulo">
          {titulo}
        </h2>
        {cards.length > 0 && <span className="secao__conta">{cards.length}</span>}
      </div>
      {cards.length ? (
        <div className="grade-cards">
          {cards.map((c) => (
            <CardProduto key={c.id} card={c} porque={"porque" in c ? c.porque : undefined} />
          ))}
        </div>
      ) : (
        <p className="secao__vazio">{vazio}</p>
      )}
    </section>
  );
}

export function Inicio() {
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    setEstado({ tipo: "carregando" });
    api
      .inicio(perfilSalvo())
      .then((dados) => setEstado({ tipo: "ok", dados }))
      .catch(() => setEstado({ tipo: "erro" }));
  }, [tentativa]);

  // Um produto aparece uma vez só na home: a primeira seção que o mostra fica com ele.
  const secoes = { pra_voce: [] as Recomendacao[], caiu: [] as Card[] };
  if (estado.tipo === "ok") {
    const vistos = new Set(estado.dados.de_olho.map((c) => c.id));
    secoes.pra_voce = estado.dados.pra_voce.filter((c) => !vistos.has(c.id));
    secoes.pra_voce.forEach((c) => vistos.add(c.id));
    secoes.caiu = estado.dados.caiu_de_preco.filter((c) => !vistos.has(c.id));
  }

  return (
    <div className="inicio">
      <header className="capa">
        <div className="capa__dentro">
          <p className="capa__marca">Sossego</p>
          <h1 className="capa__pergunta">O que você quer comprar hoje?</h1>
          <CampoBusca grande rotulo="O que você quer comprar hoje?" />
        </div>
      </header>

      <main className="inicio__corpo">
        {estado.tipo === "carregando" && <p className="secao__vazio">Carregando…</p>}
        {estado.tipo === "erro" && (
          <Aviso tipo="erro">
            <p>Não deu para carregar as ofertas.</p>
            <button type="button" className="botao botao--texto" onClick={() => setTentativa((t) => t + 1)}>
              Tentar de novo
            </button>
          </Aviso>
        )}
        {estado.tipo === "ok" && (
          <>
            <Secao id="de-olho" titulo="De olho" cards={estado.dados.de_olho}
                   vazio="Nada vigiado ainda. Abra um produto para vigiar o preço." />
            <Secao id="pra-voce" titulo="Pra você" cards={secoes.pra_voce} />
            <Secao id="caiu" titulo="Caiu de preço" cards={secoes.caiu} />
            <section className="secao" aria-labelledby="explorar">
              <h2 id="explorar" className="secao__titulo">
                Explorar
              </h2>
              <ul className="chips-categoria">
                {estado.dados.categorias.map((c) => (
                  <li key={c.slug}>
                    <Link to={`/busca?categoria=${c.slug}`} className="chip-categoria">
                      <IconeCategoria icone={c.icone} tamanho={20} />
                      {c.nome}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
      </main>
      <Rodape />
    </div>
  );
}

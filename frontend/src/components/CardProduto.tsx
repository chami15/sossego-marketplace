import { ArrowDown, ArrowUp } from "lucide-react";
import { Link } from "react-router-dom";

import type { Card } from "../api/cliente";
import { partesReais, porcento, reais } from "../formato";
import { IconeCategoria, iconeDoSlug } from "./IconeCategoria";
import { IconeLoja } from "./IconeLoja";

// Imagem do produto vem do CDN da loja: exibir é o navegador do dono pedindo
// à loja. Desligado até o dono decidir (backlog); no lugar, o ícone da categoria.
const IMAGENS_DAS_LOJAS = import.meta.env.VITE_IMAGENS_DAS_LOJAS === "sim";

function dataCurta(iso: string) {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

export function CardProduto({ card, porque }: { card: Card; porque?: string }) {
  const preco = partesReais(card.menor_preco);
  const v = card.variacao_pct;
  const caiu = v !== null && v.startsWith("-");
  const pixMenor = card.menor_pix !== null && card.menor_pix !== card.menor_preco;

  return (
    <Link to={`/produto/${card.id}`} className="card">
      <div className="card__imagem">
        {IMAGENS_DAS_LOJAS && card.imagem ? (
          <img src={card.imagem} alt="" loading="lazy" referrerPolicy="no-referrer" />
        ) : (
          <span className="card__sem-imagem">
            <IconeCategoria icone={iconeDoSlug(card.categoria)} tamanho={40} />
          </span>
        )}
        {v !== null && v !== "0.0" && card.variacao_desde && (
          <span className={`selo selo--${caiu ? "queda" : "alta"}`}>
            {caiu ? <ArrowDown size={14} strokeWidth={2.5} aria-hidden="true" /> : <ArrowUp size={14} strokeWidth={2.5} aria-hidden="true" />}
            <span className="so-leitor">{caiu ? "caiu" : "subiu"}</span>
            {porcento(v)}
            <span className="selo__desde"> desde {dataCurta(card.variacao_desde)}</span>
          </span>
        )}
      </div>
      <div className="card__corpo">
        <h3 className="card__titulo">{card.titulo}</h3>
        <p className="card__preco">
          <span className="card__moeda">R$</span>
          {preco.inteiro}
          <span className="card__centavos">,{preco.centavos}</span>
        </p>
        {pixMenor && <p className="card__pix">Pix {reais(card.menor_pix!)}</p>}
        <p className="card__loja">
          <IconeLoja nome={card.loja_nome} icone={card.loja_icone} tamanho={20} />
          {card.loja_nome}
        </p>
        {card.outras_lojas > 0 && card.outras_a_partir && (
          <p className="card__outras">
            +{card.outras_lojas} {card.outras_lojas === 1 ? "loja" : "lojas"} a partir de {reais(card.outras_a_partir)}
          </p>
        )}
        {porque && <p className="card__porque">{porque}</p>}
      </div>
    </Link>
  );
}

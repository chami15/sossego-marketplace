import { ArrowDown, ArrowUp, Eye } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import type { Card } from "../api/cliente";
import { dataCurta, partesReais, porcento, reais } from "../formato";
import { useVigias } from "../vigias";
import { IconeCategoria, iconeDoSlug } from "./IconeCategoria";
import { ImagemProduto } from "./ImagemProduto";
import { IconeLoja } from "./IconeLoja";

/** Selo de variação contra o NOSSO histórico (nunca o "de" da loja): seta + %, não só cor. */
export function SeloVariacao({ pct, desde }: { pct: string | null; desde: string | null }) {
  if (pct === null || !desde || Number.parseFloat(pct) === 0) return null;
  const caiu = pct.startsWith("-");
  const Seta = caiu ? ArrowDown : ArrowUp;
  return (
    <span className={`selo selo--${caiu ? "queda" : "alta"}`}>
      <Seta size={14} strokeWidth={2.5} aria-hidden="true" />
      <span className="so-leitor">{caiu ? "caiu" : "subiu"} </span>
      {porcento(pct)}
      <span className="selo__desde"> desde {dataCurta(desde)}</span>
    </span>
  );
}

/** Preço grande: centavos menores e sobrescritos no visual; o texto lido é "R$ 4.289,00". */
export function PrecoGrande({ valor, classe = "card__preco" }: { valor: string; classe?: string }) {
  const p = partesReais(valor);
  return (
    <p className={`${classe} display`}>
      <span className="so-leitor">{p.texto}</span>
      <span aria-hidden="true">
        <span className="preco__moeda">R$</span>
        {p.inteiro}
        <span className="preco__centavos">{p.centavos}</span>
      </span>
    </p>
  );
}

export function BotaoVigiar({ produto, titulo, classe }: { produto: number; titulo: string; classe: string }) {
  const v = useVigias();
  const [ocupado, setOcupado] = useState(false);
  if (!v.disponivel) return null;
  const ligado = v.vigiado(produto);
  return (
    <button
      type="button"
      className={`${classe} ${ligado ? `${classe}--ligado` : ""}`}
      aria-pressed={ligado}
      aria-label={ligado ? `Parar de vigiar ${titulo}` : `Vigiar o preço de ${titulo}`}
      title={ligado ? "Vigiando" : "Vigiar preço"}
      disabled={ocupado}
      onClick={async () => {
        setOcupado(true);
        try {
          await v.alternar(produto);
        } finally {
          setOcupado(false);
        }
      }}
    >
      <Eye size={20} strokeWidth={ligado ? 2.25 : 1.75} aria-hidden="true" />
    </button>
  );
}

// Vitrine: a imagem é a protagonista. O link cobre o card inteiro (::after no
// título); o botão vigiar fica por cima e não abre o produto.
export function CardProduto({ card, porque }: { card: Card; porque?: string }) {
  const pixMenor = card.menor_pix !== null && card.menor_pix !== card.menor_preco;
  const [semImagem, setSemImagem] = useState(!card.imagem_local);

  return (
    <article className="card">
      <div className="card__imagem">
        {semImagem ? (
          <IconeCategoria icone={iconeDoSlug(card.categoria)} tamanho={48} />
        ) : (
          <ImagemProduto src={card.imagem_local!} alt="" loading="lazy" onError={() => setSemImagem(true)} />
        )}
        <BotaoVigiar produto={card.id} titulo={card.titulo} classe="card__vigiar" />
      </div>
      <div className="card__corpo">
        <SeloVariacao pct={card.variacao_pct} desde={card.variacao_desde} />
        <PrecoGrande valor={card.menor_preco} />
        {pixMenor && <p className="card__pix">Pix {reais(card.menor_pix!)}</p>}
        <h3 className="card__titulo">
          <Link to={`/produto/${card.id}`} className="card__link">
            {card.titulo}
          </Link>
        </h3>
        <p className="card__loja">
          <IconeLoja slug={card.loja} nome={card.loja_nome} tamanho={20} />
          {card.loja_nome}
        </p>
        {card.outras_lojas > 0 && card.outras_a_partir && (
          <p className="card__outras">
            +{card.outras_lojas} {card.outras_lojas === 1 ? "loja" : "lojas"} a partir de {reais(card.outras_a_partir)}
          </p>
        )}
        {porque && <p className="card__porque">{porque}</p>}
      </div>
    </article>
  );
}

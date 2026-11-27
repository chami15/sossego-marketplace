import { ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { Rodape, Topo } from "../../components/Topo";
import { IconeLoja } from "../../components/IconeLoja";
import { reais } from "../../formato";
import "./produto.css";

interface Oferta {
  anuncio_id: number;
  loja_nome: string;
  loja_icone: string | null;
  url: string;
  preco: string;
  preco_pix: string | null;
  desatualizada: boolean;
}

// Provisória: a página do produto (histórico, calculadora, vigiar) é a Fase 8.
// Aqui o card já tem para onde ir: as ofertas, com link para a loja.
export function ProdutoProvisorio() {
  const { id } = useParams();
  const [p, setP] = useState<{ titulo: string; ofertas: Oferta[] } | null | "erro">(null);

  useEffect(() => {
    fetch(`/api/v1/produtos/${id}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setP)
      .catch(() => setP("erro"));
  }, [id]);

  return (
    <div className="pagina">
      <Topo />
      <main className="produto">
        {p === null && <p>Carregando…</p>}
        {p === "erro" && <p>Produto não encontrado.</p>}
        {p && p !== "erro" && (
          <>
            <h1 className="produto__titulo">{p.titulo}</h1>
            <ul className="ofertas">
              {p.ofertas.map((o) => (
                <li key={o.anuncio_id} className={`oferta ${o.desatualizada ? "oferta--velha" : ""}`}>
                  <IconeLoja nome={o.loja_nome} icone={o.loja_icone} tamanho={24} />
                  <span className="oferta__loja">{o.loja_nome}</span>
                  <span className="oferta__preco">{reais(o.preco)}</span>
                  <span className="oferta__pix">{o.preco_pix && o.preco_pix !== o.preco ? `Pix ${reais(o.preco_pix)}` : ""}</span>
                  <a href={o.url} target="_blank" rel="noopener noreferrer" className="oferta__link">
                    Ver na loja
                    <ExternalLink size={16} strokeWidth={1.75} aria-hidden="true" />
                  </a>
                </li>
              ))}
            </ul>
          </>
        )}
      </main>
      <Rodape />
    </div>
  );
}

import { siAliexpress, siCarrefour, siLeroymerlin, siShopee, type SimpleIcon } from "simple-icons";

interface Props {
  slug: string;
  nome: string;
  tamanho?: number;
}

// Marcas do pacote simple-icons (SVG, CC0, no bundle: zero requisição). Conferido
// em 27/11 na 16.38.1: só estas 4 das nossas lojas existem lá. As outras ficam
// com o monograma, que identifica a loja sem imitar a marca. Nada de favicon.
const MARCAS: Record<string, SimpleIcon> = {
  aliexpress: siAliexpress,
  carrefour: siCarrefour,
  "leroy-merlin": siLeroymerlin,
  shopee: siShopee,
};

export function IconeLoja({ slug, nome, tamanho = 28 }: Props) {
  const estilo = { width: tamanho, height: tamanho };
  const marca = MARCAS[slug];
  if (marca) {
    // Monocromática no azul do Sossego: a marca é reconhecível pelo desenho,
    // sem a cor de cada loja brigar com a página.
    return (
      <span className="icone-loja icone-loja--marca" style={estilo} aria-hidden="true">
        <svg viewBox="0 0 24 24" width={tamanho * 0.64} height={tamanho * 0.64} focusable="false">
          <path d={marca.path} fill="currentColor" />
        </svg>
      </span>
    );
  }
  const letras = nome
    .replace(/[^\p{L}\p{N} ]/gu, " ") // "C&A" vira "CA"
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
  return (
    <span className="icone-loja icone-loja--monograma" style={estilo} aria-hidden="true">
      {letras}
    </span>
  );
}

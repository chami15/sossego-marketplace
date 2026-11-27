import { useState } from "react";

interface Props {
  nome: string;
  icone: string | null;
  tamanho?: number;
}

// Ícone servido de /public (nunca hotlink). Enquanto o arquivo da loja não foi
// baixado, mostra o monograma: identifica a loja sem imitar a marca.
export function IconeLoja({ nome, icone, tamanho = 28 }: Props) {
  const [falhou, setFalhou] = useState(false);
  const estilo = { width: tamanho, height: tamanho };
  if (icone && !falhou) {
    return <img className="icone-loja" src={`/${icone}`} alt="" style={estilo} onError={() => setFalhou(true)} />;
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

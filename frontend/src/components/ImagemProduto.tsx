import { useState, type ImgHTMLAttributes } from "react";

// Imagem de produto que nunca estica além de 2x o tamanho real: a capa de 75 px
// da Ludopedia fica com 150 px, centralizada no fundo cinza, em vez de borrada
// ocupando o quadro todo. O CSS dá o tamanho (84% do quadro, contain); aqui só
// entra o teto em px depois de saber o tamanho real.
export function ImagemProduto(props: ImgHTMLAttributes<HTMLImageElement>) {
  const [teto, setTeto] = useState<{ maxWidth: number; maxHeight: number } | null>(null);
  return (
    <img
      decoding="async"
      {...props}
      style={teto ? { ...props.style, ...teto } : props.style}
      onLoad={(e) => {
        const { naturalWidth: w, naturalHeight: h } = e.currentTarget;
        if (w && h) setTeto({ maxWidth: 2 * w, maxHeight: 2 * h });
        props.onLoad?.(e);
      }}
    />
  );
}

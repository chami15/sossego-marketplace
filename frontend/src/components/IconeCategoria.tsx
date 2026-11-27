// Ícones de traço próprios (24×24, traço 1,5, pontas retas), no mesmo tom
// institucional do resto. Chave = categoria.icone da migration 004.
const DESENHOS: Record<string, string> = {
  geladeira: "M6 2.75h12v18.5H6z M6 9.25h12 M9 5v2 M9 11.5v3",
  tv: "M2.75 5.75h18.5v11.5H2.75z M8 21.25h8 M12 17.25v4",
  controle:
    "M6.5 7.75h11a4 4 0 0 1 3.9 3.1l1 4.6a2.6 2.6 0 0 1-4.6 2.1l-1.8-2.3h-8l-1.8 2.3a2.6 2.6 0 0 1-4.6-2.1l1-4.6a4 4 0 0 1 3.9-3.1z M7.5 10.5v3 M6 12h3 M15.5 11h.01 M17.5 13h.01",
  dado: "M3.75 3.75h16.5v16.5H3.75z M8 8h.01 M16 8h.01 M12 12h.01 M8 16h.01 M16 16h.01",
  notebook: "M4.75 5.75h14.5v10H4.75z M2 18.25h20",
  camiseta: "M8.5 3.25 3 6.25l2 4 2-1v11.5h10V9.25l2 1 2-4-5.5-3a3.5 3.5 0 0 1-7 0z",
  tenis: "M2.75 17.25V9.5l4.5-1.75 2.5 3.5 5 1.25 6.5 2v2.75z M2.75 20.25h18.5 M9.75 11.25l1.5-1.5 M12 12l1.5-1.5",
  frasco: "M10 2.75h4v3h-4z M8.75 5.75h6.5v3l2 2v10.5H6.75V10.75l2-2z M6.75 13.5h10.5",
  casa: "M3.25 10.5 12 3.25l8.75 7.25 M5.75 8.75v12.5h12.5V8.75 M10 21.25v-6h4v6",
  urso:
    "M7.5 4.25a2.5 2.5 0 1 0 0 5 M16.5 4.25a2.5 2.5 0 1 1 0 5 M12 5.25a6 6 0 0 1 6 6v3a6 6 0 0 1-12 0v-3a6 6 0 0 1 6-6z M10 11h.01 M14 11h.01 M10.5 15h3",
  livro: "M12 6.25c-2.5-1.75-5.5-2-8.75-1.5v14c3.25-.5 6.25-.25 8.75 1.5 2.5-1.75 5.5-2 8.75-1.5v-14c-3.25-.5-6.25-.25-8.75 1.5z M12 6.25v14",
  bola: "M12 2.75a9.25 9.25 0 1 0 0 18.5 9.25 9.25 0 1 0 0-18.5z M2.75 12h18.5 M12 2.75c3 2.75 3 15.75 0 18.5 M12 2.75c-3 2.75-3 15.75 0 18.5",
};

export function IconeCategoria({ icone, tamanho = 28 }: { icone: string; tamanho?: number }) {
  return (
    <svg
      width={tamanho}
      height={tamanho}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="square"
      strokeLinejoin="miter"
      aria-hidden="true"
    >
      <path d={DESENHOS[icone] ?? DESENHOS.casa} />
    </svg>
  );
}

import type { ReactNode } from "react";

interface Props {
  selecionado: boolean;
  onAlternar: () => void;
  children: ReactNode;
}

// Botão de alternar: o estado vai em aria-pressed e num ✓ visível, não só na cor.
export function Chip({ selecionado, onAlternar, children }: Props) {
  return (
    <button type="button" className="chip" aria-pressed={selecionado} onClick={onAlternar}>
      <span className="chip__marca" aria-hidden="true">
        {selecionado ? "✓" : ""}
      </span>
      {children}
    </button>
  );
}

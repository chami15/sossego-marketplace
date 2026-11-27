import { Check } from "lucide-react";
import type { ReactNode } from "react";

// Controles nativos (radio/checkbox) escondidos atrás do visual: o navegador dá
// papel, teclado (setas no radio, espaço no checkbox) e leitor de tela de graça.

interface Unica {
  nome: string;
  marcado: boolean;
  onEscolher: () => void;
  children: ReactNode;
}

/** Escolha única: sem caixinha; o chip inteiro preenche quando marcado. */
export function OpcaoUnica({ nome, marcado, onEscolher, children }: Unica) {
  return (
    <label className="opcao-unica">
      <input type="radio" className="so-leitor" name={nome} checked={marcado} onChange={onEscolher} />
      <span>{children}</span>
    </label>
  );
}

interface Varias {
  marcado: boolean;
  onAlternar: () => void;
  recusado?: boolean;
  className?: string;
  children: ReactNode;
}

/** Escolha múltipla: caixinha só aqui, com check sólido quando marcada. */
export function OpcaoVarias({ marcado, onAlternar, recusado, className = "", children }: Varias) {
  return (
    <label className={`opcao-varias ${recusado ? "tremor" : ""} ${className}`}>
      <input type="checkbox" className="so-leitor" checked={marcado} onChange={onAlternar} />
      {children}
      <span className="caixa" aria-hidden="true">
        {marcado && <Check size={14} strokeWidth={3} />}
      </span>
    </label>
  );
}

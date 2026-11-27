import { Search } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { buscasRecentes, lembrarBusca } from "../buscasRecentes";

interface Props {
  inicial?: string;
  grande?: boolean;
  rotulo?: string;
}

// Busca com autocomplete das buscas recentes deste navegador (datalist nativo:
// teclado e leitor de tela de graça).
export function CampoBusca({ inicial = "", grande = false, rotulo = "Buscar produto" }: Props) {
  const [texto, setTexto] = useState(inicial);
  const navegar = useNavigate();
  const id = useId();

  function enviar(e: FormEvent) {
    e.preventDefault();
    const q = texto.trim();
    if (q.length < 2) return;
    lembrarBusca(q);
    navegar(`/busca?q=${encodeURIComponent(q)}`);
  }

  return (
    <form role="search" className={`campo-busca ${grande ? "campo-busca--grande" : ""}`} onSubmit={enviar}>
      <Search className="campo-busca__lupa" size={grande ? 24 : 20} strokeWidth={1.75} aria-hidden="true" />
      <input
        type="search"
        aria-label={rotulo}
        placeholder="PS5, Dixit, air fryer..."
        value={texto}
        list={`${id}-recentes`}
        minLength={2}
        maxLength={100}
        onChange={(e) => setTexto(e.target.value)}
      />
      <datalist id={`${id}-recentes`}>
        {buscasRecentes().map((b) => (
          <option key={b} value={b} />
        ))}
      </datalist>
      <button type="submit" className="campo-busca__ir">
        Buscar
      </button>
    </form>
  );
}

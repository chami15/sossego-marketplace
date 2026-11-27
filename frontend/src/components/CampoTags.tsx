import { X } from "lucide-react";
import { useId, useState, type KeyboardEvent } from "react";

interface Props {
  rotulo: string;
  dica: string;
  placeholder: string;
  valores: string[];
  onMudar: (v: string[]) => void;
  max?: number;
  maxCaracteres?: number;
}

// Vários termos como tags: Enter ou vírgula confirma; Backspace no vazio apaga o último.
export function CampoTags({ rotulo, dica, placeholder, valores, onMudar, max = 20, maxCaracteres = 60 }: Props) {
  const [texto, setTexto] = useState("");
  const id = useId();

  function confirmar(bruto: string) {
    const novos = bruto
      .split(",")
      .map((t) => t.trim().toLowerCase())
      .filter((t) => t && !valores.includes(t));
    if (novos.length) onMudar([...valores, ...new Set(novos)].slice(0, max));
    setTexto("");
  }

  function tecla(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      confirmar(texto);
    } else if (e.key === "Backspace" && !texto && valores.length) {
      onMudar(valores.slice(0, -1));
    }
  }

  return (
    <div className="tags">
      <label className="tags__rotulo" htmlFor={id}>
        {rotulo}
      </label>
      <p className="tags__dica" id={`${id}-dica`}>
        {dica}
      </p>
      <div className="tags__caixa">
        <ul className="tags__lista" aria-label="Termos adicionados">
          {valores.map((v) => (
            <li key={v} className="tag">
              {v}
              <button
                type="button"
                className="tag__remover"
                aria-label={`Remover ${v}`}
                onClick={() => onMudar(valores.filter((x) => x !== v))}
              >
                <X size={14} strokeWidth={2} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
        <input
          id={id}
          className="tags__entrada"
          value={texto}
          maxLength={maxCaracteres}
          placeholder={valores.length ? "" : placeholder}
          aria-describedby={`${id}-dica`}
          onChange={(e) => (e.target.value.includes(",") ? confirmar(e.target.value) : setTexto(e.target.value))}
          onKeyDown={tecla}
          onBlur={() => texto.trim() && confirmar(texto)}
        />
      </div>
    </div>
  );
}

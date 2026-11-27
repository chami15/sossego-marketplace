import type { ReactNode } from "react";

interface Props {
  tipo: "info" | "erro";
  children: ReactNode;
}

// "info" é discreto e anunciado sem interromper (status); "erro" interrompe (alert).
export function Aviso({ tipo, children }: Props) {
  return (
    <div className={`aviso aviso--${tipo}`} role={tipo === "erro" ? "alert" : "status"}>
      <span className="aviso__icone" aria-hidden="true">
        {tipo === "erro" ? "!" : "i"}
      </span>
      <div>{children}</div>
    </div>
  );
}

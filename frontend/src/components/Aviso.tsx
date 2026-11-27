import { CircleAlert, Info } from "lucide-react";
import type { ReactNode } from "react";

interface Props {
  tipo: "info" | "erro";
  children: ReactNode;
}

// "info" é discreto e anunciado sem interromper (status); "erro" interrompe (alert).
export function Aviso({ tipo, children }: Props) {
  const Icone = tipo === "erro" ? CircleAlert : Info;
  return (
    <div className={`aviso aviso--${tipo}`} role={tipo === "erro" ? "alert" : "status"}>
      <Icone className="aviso__icone" size={20} strokeWidth={1.75} aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}

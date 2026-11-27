import type { ButtonHTMLAttributes } from "react";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: "primario" | "secundario" | "texto";
}

export function Botao({ variante = "primario", className = "", type = "button", ...resto }: Props) {
  return <button type={type} className={`botao botao--${variante} ${className}`} {...resto} />;
}

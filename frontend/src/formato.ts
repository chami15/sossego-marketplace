// Formata dinheiro e percentuais a partir da string decimal da API, sem passar
// por float (regra do projeto: dinheiro nunca é float).

export function reais(valor: string): string {
  const negativo = valor.startsWith("-");
  const [inteiro, frac = ""] = valor.replace("-", "").split(".");
  const milhar = inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  // Espaço inseparável: "R$" nunca fica sozinho no fim da linha.
  return `${negativo ? "−" : ""}R$ ${milhar},${(frac + "00").slice(0, 2)}`;
}

/** Só a parte inteira e os centavos separados, para o preço grande do card. */
export function partesReais(valor: string): { inteiro: string; centavos: string } {
  const [inteiro, frac = ""] = valor.split(".");
  return { inteiro: inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, "."), centavos: (frac + "00").slice(0, 2) };
}

/** "-12.3" → "12,3%" (o sinal vira seta no selo, nunca só cor). */
export function porcento(valor: string): string {
  return `${valor.replace("-", "").replace(".", ",")}%`;
}

export function haQuanto(iso: string, agora = Date.now()): string {
  const min = Math.round((agora - new Date(iso).getTime()) / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  const h = Math.round(min / 60);
  if (h < 48) return `há ${h} h`;
  return `há ${Math.round(h / 24)} dias`;
}

// Formatador único de dinheiro e percentual, em pt-BR pelo Intl. A API manda
// dinheiro como string decimal ("4289.00"); o Intl aceita a string e formata
// sem passar por float (regra do projeto: dinheiro nunca é float).

const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });


// O tipo do lib aceita number; a especificação (Intl.NumberFormat v3) aceita a
// string decimal e mantém a precisão. O cast é só para o compilador.
type Decimal = string;
const comoNumero = (v: Decimal) => v as unknown as number;

/** "4289.00" → "R$ 4.289,00" (o espaço é inseparável). */
export function reais(valor: Decimal): string {
  return BRL.format(comoNumero(valor));
}

/** Preço grande do card: inteiro e centavos separados para o visual; `texto` é o que se lê. */
export function partesReais(valor: Decimal): { inteiro: string; centavos: string; texto: string } {
  const partes = BRL.formatToParts(comoNumero(valor));
  const inteiro = partes
    .filter((p) => p.type === "integer" || p.type === "group")
    .map((p) => p.value)
    .join("");
  const centavos = partes.find((p) => p.type === "fraction")?.value ?? "00";
  return { inteiro, centavos, texto: reais(valor) };
}

/** "19.9" → 1990n: comparar e somar dinheiro em centavos inteiros, sem float. */
export function centavos(valor: Decimal): bigint {
  const negativo = valor.startsWith("-");
  const [inteiro, frac = ""] = valor.replace("-", "").split(".");
  const c = BigInt(inteiro || "0") * 100n + BigInt((frac + "00").slice(0, 2));
  return negativo ? -c : c;
}

/** 430890n → "4308.90" (de volta ao formato da API). */
export function deCentavos(c: bigint): Decimal {
  const s = (c < 0n ? -c : c).toString().padStart(3, "0");
  return `${c < 0n ? "-" : ""}${s.slice(0, -2)}.${s.slice(-2)}`;
}

const NUM = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** "4289.00" → "4.289,00": valor de campo de formulário, sem o "R$". */
export function numeroBR(valor: Decimal): string {
  return NUM.format(comoNumero(valor));
}

/** "4.289,00" (o que a pessoa digitou) → "4289.00"; null se não for valor.
 *  Em pt-BR o ponto é milhar e a vírgula separa até 2 casas de centavos. */
export function deNumeroBR(texto: string): Decimal | null {
  const limpo = texto.replace(/[R$\s]/g, "").replace(/\./g, "");
  const m = /^(\d+)(?:,(\d{1,2}))?$/.exec(limpo);
  return m ? `${BigInt(m[1])}.${(m[2] ?? "").padEnd(2, "0")}` : null;
}

/** "-12.3" → "12,3%" (o sinal vira seta no selo, nunca só cor). */
export function porcento(valor: Decimal, casas = 1): string {
  const fmt = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: casas });
  return `${fmt.format(comoNumero(valor.replace("-", "")))}%`;
}

export function haQuanto(iso: string, agora = Date.now()): string {
  const min = Math.round((agora - new Date(iso).getTime()) / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  const h = Math.round(min / 60);
  if (h < 48) return `há ${h} h`;
  return `há ${Math.round(h / 24)} dias`;
}

/** "2026-11-24" → "24/11" (data do banco, sem fuso: não passa por Date). */
export function dataCurta(iso: string): string {
  const [, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}`;
}

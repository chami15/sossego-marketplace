import { useEffect, useState } from "react";

import { api, ErroApi, type Simulacao } from "../../api/cliente";
import { porcento, reais } from "../../formato";

// Calculadora de pagamento (Fase 5): Pix agora × parcelado, em reais de hoje,
// com o CDI do Banco Central salvo pelo worker. Começa com a melhor oferta.
interface Props {
  avista: string;
  cartao: string;
  parcelas: number;
}

const paraDecimal = (texto: string) => {
  const limpo = texto.replace(/[^\d,]/g, "").replace(",", ".");
  return /^\d+(\.\d{1,2})?$/.test(limpo) ? limpo : "";
};
const paraTela = (d: string) => d.replace(".", ",");

// A API devolve Pix e cada nº de parcelas (até 11 linhas). Na lateral bastam a
// melhor, o Pix e o parcelamento máximo: o resto fica entre esses dois.
function resumo(s: Simulacao) {
  const [melhor, ...resto] = s.opcoes;
  const pix = resto.find((o) => o.tipo === "pix");
  const maximo = resto.filter((o) => o.tipo !== "pix").sort((a, b) => (b.parcelas ?? 0) - (a.parcelas ?? 0))[0];
  return [melhor, pix, maximo].filter((o, i, xs): o is Simulacao["opcoes"][number] => Boolean(o) && xs.indexOf(o) === i);
}

export function Calculadora({ avista, cartao, parcelas }: Props) {
  const [campos, setCampos] = useState({ avista: paraTela(avista), cartao: paraTela(cartao), parcelas: String(parcelas) });
  const [r, setR] = useState<Simulacao | null | "erro" | "sem-taxa">(null);

  useEffect(() => {
    const e = { preco_avista: paraDecimal(campos.avista), preco_cartao: paraDecimal(campos.cartao), parcelas: Number(campos.parcelas) };
    if (!e.preco_avista || !e.preco_cartao || !(e.parcelas >= 1 && e.parcelas <= 24)) return;
    let vivo = true;
    const t = setTimeout(() => {
      api
        .simular(e)
        .then((s) => vivo && setR(s))
        .catch((x) => vivo && setR(x instanceof ErroApi && x.status === 503 ? "sem-taxa" : "erro"));
    }, 250);
    return () => {
      vivo = false;
      clearTimeout(t);
    };
  }, [campos]);

  return (
    <section className="calc" aria-labelledby="calc-titulo">
      <h2 id="calc-titulo" className="lateral__titulo">
        Pix ou parcelado?
      </h2>
      <div className="calc__campos">
        <label>
          <span>No Pix (R$)</span>
          <input inputMode="decimal" value={campos.avista} onChange={(e) => setCampos({ ...campos, avista: e.target.value })} />
        </label>
        <label>
          <span>No cartão (R$)</span>
          <input inputMode="decimal" value={campos.cartao} onChange={(e) => setCampos({ ...campos, cartao: e.target.value })} />
        </label>
        <label>
          <span>Parcelas sem juros</span>
          <input
            type="number"
            min={1}
            max={24}
            value={campos.parcelas}
            onChange={(e) => setCampos({ ...campos, parcelas: e.target.value })}
          />
        </label>
      </div>
      <div aria-live="polite">
        {r === "sem-taxa" && <p className="calc__nota">Sem a taxa do Banco Central ainda: o worker busca 1x por dia.</p>}
        {r === "erro" && <p className="calc__nota">Não deu para calcular agora.</p>}
        {r && typeof r === "object" && (
          <>
            <p className="calc__veredito">{r.recomendacao}</p>
            <dl className="calc__opcoes">
              {resumo(r).map((o) => (
                <div key={`${o.tipo}-${o.parcelas ?? 0}`} className={o === r.opcoes[0] ? "calc__opcao calc__opcao--melhor" : "calc__opcao"}>
                  <dt>{o.tipo === "pix" ? "Pix" : `${o.parcelas}x de ${reais(o.valor_parcela!)}`}</dt>
                  <dd>
                    {reais(o.custo_efetivo)} <span>em valor de hoje</span>
                  </dd>
                </div>
              ))}
            </dl>
            {r.cdi_anual_pct && r.cdi_data && (
              <p className="calc__nota">
                CDI {porcento(r.cdi_anual_pct, 2)} a.a. (Banco Central, {r.cdi_data.split("-").reverse().join("/")})
              </p>
            )}
          </>
        )}
      </div>
    </section>
  );
}

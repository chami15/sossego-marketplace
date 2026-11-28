import { useEffect, useMemo, useRef, useState } from "react";

import type { Historico, Ponto } from "../../api/cliente";
import { centavos, dataCurta, deCentavos, reais } from "../../formato";

// Preço no tempo em degrau (o preço vale até a próxima coleta). Uma cor por
// LOJA, na ordem fixa da paleta validada (skill dataviz: 3 primeiros slots
// passam CVD em todos os pares); a 4ª loja em diante vira cinza "outras".
// Menor preço geral é uma faixa cinza larga POR BAIXO das lojas (tracejada por
// cima escondia a loja que é o menor). Um eixo só. Cor nunca sozinha: legenda,
// tooltip com nome e tabela. O viewBox acompanha a largura real, para o texto
// do eixo não encolher junto com o SVG.
const CORES = ["#2a78d6", "#eb6834", "#1baf7a"];
const OUTRAS = "#8a8f9c";
const L_PADRAO = 560;
const A = 240;
const M = { esq: 56, dir: 12, topo: 12, base: 28 };

interface Linha {
  chave: string;
  rotulo: string;
  cor: string;
  faixa?: boolean;
  pontos: { t: number; c: bigint }[];
}

const hora = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

// Valor de uma série em degrau no instante t: o último ponto até t.
function valorEm(l: Linha, t: number): bigint | null {
  let v: bigint | null = null;
  for (const p of l.pontos) {
    if (p.t > t) break;
    v = p.c;
  }
  return v;
}

export function GraficoPreco({ h, nomes }: { h: Historico; nomes: Record<string, string> }) {
  const [mira, setMira] = useState<number | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const [L, setL] = useState(L_PADRAO);

  useEffect(() => {
    const el = svg.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setL(Math.max(280, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  });

  const linhas = useMemo<Linha[]>(() => {
    const conv = (ps: Ponto[]) => ps.map((p) => ({ t: new Date(p.em).getTime(), c: centavos(p.preco) }));
    // Cor segue a loja (ordem alfabética do slug), não o ranking de preço.
    const lojas = [...new Set(h.series.map((s) => s.loja))].sort();
    const porLoja = new Map<string, Linha>();
    for (const s of h.series) {
      const i = lojas.indexOf(s.loja);
      const existente = porLoja.get(s.loja);
      // Dois anúncios da mesma loja: os pontos dos dois entram na mesma linha, em ordem de tempo.
      const pontos = conv(s.pontos);
      if (existente) existente.pontos = [...existente.pontos, ...pontos].sort((a, b) => a.t - b.t);
      else
        porLoja.set(s.loja, {
          chave: s.loja,
          rotulo: nomes[s.loja] ?? s.loja,
          cor: CORES[i] ?? OUTRAS,
          pontos,
        });
    }
    const resultado = [...porLoja.values()];
    if (h.series.length > 1 && h.menor_geral.length)
      resultado.unshift({ chave: "menor", rotulo: "Menor preço geral", cor: "var(--linha-forte)", faixa: true, pontos: conv(h.menor_geral) });
    return resultado;
  }, [h, nomes]);

  const todos = linhas.flatMap((l) => l.pontos);
  const instantes = [...new Set(todos.map((p) => p.t))].sort((a, b) => a - b);

  if (instantes.length <= 1) {
    const p = h.menor_geral[0] ?? h.series[0]?.pontos[0];
    return (
      <div className="grafico grafico--um-ponto">
        <svg viewBox={`0 0 ${L_PADRAO} 80`} role="img" aria-label={p ? `Um preço registrado: ${reais(p.preco)}` : "Sem preço registrado"}>
          <line x1={M.esq} x2={L_PADRAO - M.dir} y1={40} y2={40} className="grafico__grade" />
          {p && <circle cx={L_PADRAO / 2} cy={40} r={6} fill={CORES[0]} stroke="var(--branco)" strokeWidth={2} />}
        </svg>
        <p className="grafico__aviso">Começamos a acompanhar hoje. Volte amanhã para ver a variação.</p>
      </div>
    );
  }

  const t0 = instantes[0];
  const t1 = Math.max(Date.now(), instantes[instantes.length - 1]);
  let min = todos.reduce((a, p) => (p.c < a ? p.c : a), todos[0].c);
  let max = todos.reduce((a, p) => (p.c > a ? p.c : a), todos[0].c);
  const folga = (max - min) / 8n || 100n;
  min -= folga;
  max += folga;
  const x = (t: number) => M.esq + ((t - t0) / (t1 - t0)) * (L - M.esq - M.dir);
  // Só a ESCALA de pixel vira número; o valor exibido continua em centavos exatos.
  const y = (c: bigint) => M.topo + (Number(max - c) / Number(max - min)) * (A - M.topo - M.base);

  const caminho = (l: Linha) => {
    let d = "";
    l.pontos.forEach((p, i) => {
      d += i === 0 ? `M${x(p.t)},${y(p.c)}` : `H${x(p.t)}V${y(p.c)}`;
    });
    const ultimo = l.pontos[l.pontos.length - 1];
    return ultimo ? `${d}H${x(t1)}` : d;
  };

  const marcas = [min + folga, (min + max) / 2n, max - folga];
  const datas = [t0, (t0 + t1) / 2, t1];

  function mover(e: React.PointerEvent<SVGSVGElement>) {
    const r = svg.current!.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * L;
    // Mira encaixa no instante com dado mais próximo.
    let melhor = instantes[0];
    for (const t of instantes) if (Math.abs(x(t) - px) < Math.abs(x(melhor) - px)) melhor = t;
    setMira(melhor);
  }

  const dica = mira === null ? null : linhas.map((l) => ({ l, v: valorEm(l, mira) })).filter((d) => d.v !== null);

  return (
    <div className="grafico">
      <ul className="grafico__legenda">
        {linhas.map((l) => (
          <li key={l.chave}>
            <svg width="18" height="8" aria-hidden="true">
              <line x1="0" x2="18" y1="4" y2="4" stroke={l.cor} strokeWidth={l.faixa ? 6 : 2} />
            </svg>
            {l.rotulo}
          </li>
        ))}
      </ul>
      <div className="grafico__area">
        <svg
          ref={svg}
          viewBox={`0 0 ${L} ${A}`}
          role="img"
          aria-label={`Preço no tempo, ${linhas.length} séries. A tabela abaixo tem os valores.`}
          onPointerMove={mover}
          onPointerLeave={() => setMira(null)}
        >
          {marcas.map((c) => (
            <g key={String(c)}>
              <line x1={M.esq} x2={L - M.dir} y1={y(c)} y2={y(c)} className="grafico__grade" />
              <text x={M.esq - 8} y={y(c)} className="grafico__eixo" textAnchor="end" dominantBaseline="middle">
                {reais(deCentavos((c / 100n) * 100n)).replace(",00", "")}
              </text>
            </g>
          ))}
          {datas.map((t, i) => (
            <text key={t} x={x(t)} y={A - 8} className="grafico__eixo" textAnchor={(["start", "middle", "end"] as const)[i]}>
              {dataCurta(new Date(t).toISOString())}
            </text>
          ))}
          {linhas.map((l) => (
            <path
              key={l.chave}
              d={caminho(l)}
              fill="none"
              stroke={l.cor}
              strokeWidth={l.faixa ? 8 : 2}
              strokeLinejoin="round"
            />
          ))}
          {mira !== null && (
            <g>
              <line x1={x(mira)} x2={x(mira)} y1={M.topo} y2={A - M.base} className="grafico__mira" />
              {dica!.map(({ l, v }) => (
                <circle key={l.chave} cx={x(mira)} cy={y(v!)} r={4} fill={l.cor} stroke="var(--branco)" strokeWidth={2} />
              ))}
            </g>
          )}
        </svg>
        {mira !== null && dica!.length > 0 && (
          <div className="grafico__dica" style={{ left: `${(x(mira) / L) * 100}%` }} role="status">
            <p className="grafico__dica-data">{hora(new Date(mira).toISOString())}</p>
            {dica!.map(({ l, v }) => (
              <p key={l.chave}>
                <svg width="12" height="4" aria-hidden="true">
                  <line x1="0" x2="12" y1="2" y2="2" stroke={l.cor} strokeWidth="2" />
                </svg>
                {l.rotulo} <strong>{reais(deCentavos(v!))}</strong>
              </p>
            ))}
          </div>
        )}
      </div>
      <details className="grafico__tabela">
        <summary>Ver em tabela</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">Quando</th>
              <th scope="col">Loja</th>
              <th scope="col">Preço</th>
            </tr>
          </thead>
          <tbody>
            {h.series.flatMap((s) =>
              s.pontos.map((p) => (
                <tr key={`${s.anuncio_id}-${p.em}`}>
                  <td>{hora(p.em)}</td>
                  <td>{nomes[s.loja] ?? s.loja}</td>
                  <td>{reais(p.preco)}</td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </details>
    </div>
  );
}

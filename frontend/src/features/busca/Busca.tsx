import { Ban, Check, Clock, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { api, type Categoria, type Loja, type Ordem, type ResultadoBusca, type SaudeLoja } from "../../api/cliente";
import { Aviso } from "../../components/Aviso";
import { CardProduto } from "../../components/CardProduto";
import { OpcaoUnica } from "../../components/Escolha";
import { Rodape, Topo } from "../../components/Topo";
import { haQuanto } from "../../formato";
import { perfilSalvo } from "../../perfil";
import "./busca.css";

const ORDENS: [Ordem, string][] = [
  ["relevancia", "Relevância"],
  ["preco", "Menor preço"],
  ["pix", "Menor no Pix"],
  ["queda", "Maior queda"],
];

// "1.299,90" ou "1299" → "1299.90"/"1299" (o que a API aceita); vazio se não for número.
function paraDecimal(texto: string): string {
  const limpo = texto.replace(/[^\d,]/g, "").replace(",", ".");
  return /^\d+(\.\d{1,2})?$/.test(limpo) ? limpo : "";
}

type Estado = { tipo: "carregando" } | { tipo: "erro" } | { tipo: "ok"; r: ResultadoBusca };

/** De onde vêm os preços: a situação de cada loja coletada (a busca não vai às lojas). */
function Coletas({ lojas }: { lojas: SaudeLoja[] }) {
  const ativas = lojas.filter((l) => l.situacao !== "inativa");
  if (!ativas.length) return null;
  return (
    <ul className="coletas" aria-label="Situação das lojas coletadas">
      {ativas.map((l) => {
        const ok = l.situacao === "ok";
        const Icone = ok ? Check : l.situacao === "atrasada" ? Clock : Ban;
        return (
          <li key={l.slug} className={`coletas__loja coletas__loja--${ok ? "ok" : "alerta"}`}>
            <Icone size={14} strokeWidth={2.25} aria-hidden="true" />
            {l.nome}
            <span className="coletas__quando">{ok && l.ultima_ok ? haQuanto(l.ultima_ok) : l.situacao.replace("_", " ")}</span>
          </li>
        );
      })}
    </ul>
  );
}

export function Busca() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const categoria = params.get("categoria") ?? "";
  const ordem = (params.get("ordem") as Ordem) || "relevancia";
  const loja = params.get("loja") ?? "";
  const min = params.get("min") ?? "";
  const max = params.get("max") ?? "";

  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [lojas, setLojas] = useState<Loja[]>([]);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [saude, setSaude] = useState<SaudeLoja[]>([]);
  const [faixa, setFaixa] = useState({ min, max });

  useEffect(() => {
    api.lojas().then(setLojas).catch(() => undefined);
    api.categorias().then(setCategorias).catch(() => undefined);
    api.saude().then((s) => setSaude(s.lojas)).catch(() => undefined);
  }, []);

  useEffect(() => setFaixa({ min, max }), [min, max]);

  useEffect(() => {
    if (!q && !categoria) return;
    let vivo = true;
    setEstado({ tipo: "carregando" });
    api
      .busca({ q, categoria, ordem, lojas: loja ? [loja] : [], preco_min: min, preco_max: max, perfil: perfilSalvo() })
      .then((r) => vivo && setEstado({ tipo: "ok", r }))
      .catch(() => vivo && setEstado({ tipo: "erro" }));
    return () => {
      vivo = false;
    };
  }, [q, categoria, ordem, loja, min, max]);

  function mudar(chave: string, valor: string) {
    const p = new URLSearchParams(params);
    if (valor) p.set(chave, valor);
    else p.delete(chave);
    setParams(p, { replace: true });
  }

  function aplicarFaixa(e: FormEvent) {
    e.preventDefault();
    const p = new URLSearchParams(params);
    for (const [k, v] of [["min", faixa.min], ["max", faixa.max]] as const) {
      const d = paraDecimal(v);
      if (d) p.set(k, d);
      else p.delete(k);
    }
    setParams(p, { replace: true });
  }

  const nomeCategoria = categorias.find((c) => c.slug === categoria)?.nome ?? categoria;
  const titulo = q ? `“${q}”` : nomeCategoria;
  const temFiltro = Boolean(loja || min || max);

  return (
    <div className="pagina">
      <Topo busca={q} />
      <main className="busca">
        <div className="busca__cabeca">
          <h1 className="busca__titulo">{titulo}</h1>
          <p className="busca__total" aria-live="polite">
            {estado.tipo === "ok" &&
              `${estado.r.total} ${estado.r.total === 1 ? "produto" : "produtos"}${q && categoria ? ` em ${nomeCategoria}` : ""}`}
          </p>
          <Coletas lojas={saude} />
        </div>

        <div className="controles">
          <div className="controles__ordem" role="radiogroup" aria-label="Ordenar por">
            {ORDENS.map(([v, r]) => (
              <OpcaoUnica key={v} nome="ordem" marcado={ordem === v} onEscolher={() => mudar("ordem", v === "relevancia" ? "" : v)}>
                {r}
              </OpcaoUnica>
            ))}
          </div>
          <div className="controles__filtros">
            <div className="filtro">
              {/* Rótulo ligado por id: envolvendo o select, o nome lido seria "Loja Todas Amazon..." */}
              <label className="filtro__rotulo" htmlFor="filtro-loja">
                Loja
              </label>
              <select id="filtro-loja" value={loja} onChange={(e) => mudar("loja", e.target.value)}>
                <option value="">Todas</option>
                {lojas.map((l) => (
                  <option key={l.slug} value={l.slug}>
                    {l.nome}
                  </option>
                ))}
              </select>
            </div>
            <form className="filtro filtro--faixa" onSubmit={aplicarFaixa}>
              <span className="filtro__rotulo" id="faixa-rotulo">
                Preço (R$)
              </span>
              <input
                inputMode="decimal"
                aria-label="Preço mínimo"
                placeholder="de"
                value={faixa.min}
                onChange={(e) => setFaixa({ ...faixa, min: e.target.value })}
              />
              <input
                inputMode="decimal"
                aria-label="Preço máximo"
                placeholder="até"
                value={faixa.max}
                onChange={(e) => setFaixa({ ...faixa, max: e.target.value })}
              />
              <button type="submit" className="botao botao--secundario filtro__aplicar">
                Aplicar
              </button>
            </form>
            {temFiltro && (
              <button
                type="button"
                className="botao botao--texto filtro__limpar"
                onClick={() => {
                  const p = new URLSearchParams(params);
                  ["loja", "min", "max"].forEach((k) => p.delete(k));
                  setParams(p, { replace: true });
                }}
              >
                <X size={16} strokeWidth={2} aria-hidden="true" />
                Limpar filtros
              </button>
            )}
          </div>
        </div>

        {estado.tipo === "carregando" && <p className="busca__vazio">Carregando…</p>}
        {estado.tipo === "erro" && (
          <Aviso tipo="erro">
            <p>Não deu para buscar agora. Confira se a API está no ar.</p>
          </Aviso>
        )}
        {estado.tipo === "ok" && estado.r.total === 0 && (
          <div className="busca__vazio">
            <p className="busca__vazio-titulo">Nada no histórico{q ? ` para “${q}”` : ""}.</p>
            <p>O Sossego mostra só o que o coletor já viu nas lojas vigiadas.{temFiltro ? " Tente sem os filtros." : ""}</p>
          </div>
        )}
        {estado.tipo === "ok" && estado.r.total > 0 && (
          <div className="grade-cards">
            {estado.r.resultados.map((c) => (
              <CardProduto key={c.id} card={c} />
            ))}
          </div>
        )}
      </main>
      <Rodape />
    </div>
  );
}

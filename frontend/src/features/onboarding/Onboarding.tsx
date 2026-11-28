import { ArrowLeft, ArrowRight, Check, CircleAlert, Info, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, type Categoria, type FaixaEtaria, type Genero, type Loja, type PerfilEntrada } from "../../api/cliente";
import { Aviso } from "../../components/Aviso";
import { BarraProgresso } from "../../components/BarraProgresso";
import { Botao } from "../../components/Botao";
import { CampoTags } from "../../components/CampoTags";
import { OpcaoUnica, OpcaoVarias } from "../../components/Escolha";
import { IconeCategoria } from "../../components/IconeCategoria";
import { IconeLoja } from "../../components/IconeLoja";
import { guardarPerfil, perfilSalvo } from "../../perfil";
import "./onboarding.css";

const MAX = 3; // igual ao backend (Pydantic + trigger limite_tres)

const FAIXAS: [FaixaEtaria, string][] = [
  ["ate-17", "até 17"],
  ["18-24", "18–24"],
  ["25-34", "25–34"],
  ["35-44", "35–44"],
  ["45-59", "45–59"],
  ["60+", "60+"],
];

const GENEROS: [Genero, string][] = [
  ["feminino", "Feminino"],
  ["masculino", "Masculino"],
  ["outro", "Outro"],
  ["prefiro-nao-dizer", "Prefiro não dizer"],
];

const PASSOS = [
  { curto: "Sobre você", pergunta: "Sobre você" },
  { curto: "O que procura", pergunta: "O que você procura?" },
  { curto: "Lojas", pergunta: "Lojas de confiança" },
];

type Carga = { estado: "carregando" } | { estado: "erro" } | { estado: "ok"; categorias: Categoria[]; lojas: Loja[] };

const semAcento = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

export function Onboarding() {
  const navegar = useNavigate();
  const [passo, setPasso] = useState(1);
  const [carga, setCarga] = useState<Carga>({ estado: "carregando" });
  const [tentativa, setTentativa] = useState(0);
  const [perfilId, setPerfilId] = useState<string | null>(null);

  const [faixa, setFaixa] = useState<FaixaEtaria | null>(null);
  const [genero, setGenero] = useState<Genero | null>(null);
  const [categorias, setCategorias] = useState<string[]>([]);
  const [interesses, setInteresses] = useState<string[]>([]);
  const [lojas, setLojas] = useState<string[]>([]);
  const [filtro, setFiltro] = useState("");

  const [limite, setLimite] = useState(false);
  const [recusado, setRecusado] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [erroSalvar, setErroSalvar] = useState(false);
  const titulo = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let vivo = true;
    setCarga({ estado: "carregando" });
    Promise.all([api.categorias(), api.lojas()])
      .then(([c, l]) => vivo && setCarga({ estado: "ok", categorias: c, lojas: l }))
      .catch(() => vivo && setCarga({ estado: "erro" }));
    return () => {
      vivo = false;
    };
  }, [tentativa]);

  // "Refazer preferências": volta com as escolhas de antes, e salva por cima.
  useEffect(() => {
    const id = perfilSalvo();
    if (!id) return;
    api
      .perfil(id)
      .then((p) => {
        setPerfilId(p.id);
        setFaixa(p.faixa_etaria);
        setGenero(p.genero);
        setCategorias(p.categorias);
        setInteresses(p.interesses);
        setLojas(p.lojas);
      })
      .catch(() => undefined); // perfil sumiu do banco: começa um novo
  }, []);

  // O tremor dura uma vez; limpa para poder tremer de novo no próximo clique.
  useEffect(() => {
    if (!recusado) return;
    const t = setTimeout(() => setRecusado(null), 400);
    return () => clearTimeout(t);
  }, [recusado]);

  // Leitor de tela e teclado começam pela pergunta nova.
  useEffect(() => {
    titulo.current?.focus();
  }, [passo]);

  const nomes = useMemo(() => {
    const m = new Map<string, string>();
    if (carga.estado === "ok") {
      carga.categorias.forEach((c) => m.set(`c:${c.slug}`, c.nome));
      carga.lojas.forEach((l) => m.set(`l:${l.slug}`, l.nome));
    }
    return m;
  }, [carga]);

  function alternar(lista: string[], setLista: (v: string[]) => void, slug: string) {
    if (lista.includes(slug)) {
      setLista(lista.filter((s) => s !== slug));
      setLimite(false);
    } else if (lista.length >= MAX) {
      // A mais antiga não sai sozinha: avisa na barra de ações e treme o item recusado.
      setLimite(true);
      setRecusado(null);
      requestAnimationFrame(() => setRecusado(slug));
    } else {
      setLista([...lista, slug]);
      setLimite(false);
    }
  }

  function irPara(n: number) {
    setLimite(false);
    setErroSalvar(false);
    setPasso(n);
    window.scrollTo({ top: 0 });
  }

  async function concluir() {
    if (!faixa) return;
    const entrada: PerfilEntrada = { faixa_etaria: faixa, genero, categorias, lojas, interesses };
    setSalvando(true);
    setErroSalvar(false);
    try {
      const p = perfilId ? await api.salvarPerfil(perfilId, entrada) : await api.criarPerfil(entrada);
      guardarPerfil(p.id);
      navegar("/", { replace: true });
    } catch {
      setErroSalvar(true);
    } finally {
      setSalvando(false);
    }
  }

  const opcoesProntas = passo === 1 || carga.estado === "ok";
  const resumo: [string, string][] = [
    ["Idade", FAIXAS.find(([v]) => v === faixa)?.[1] ?? ""],
    ["Gênero", GENEROS.find(([v]) => v === genero)?.[1] ?? ""],
    ["Categorias", categorias.map((s) => nomes.get(`c:${s}`) ?? s).join(", ")],
    ["Termos", interesses.join(", ")],
    ["Lojas", lojas.map((s) => nomes.get(`l:${s}`) ?? s).join(", ")],
  ];
  const resumoPreenchido = resumo.filter(([, v]) => v);

  const lojasVisiveis =
    carga.estado === "ok" ? carga.lojas.filter((l) => semAcento(l.nome).includes(semAcento(filtro.trim()))) : [];

  return (
    <div className="onb">
      <aside className="painel">
        <div className="painel__topo">
          <p className="painel__marca">Sossego</p>
          <p className="painel__contador">Passo {passo} de 3</p>
        </div>
        <h1 ref={titulo} tabIndex={-1} className="painel__pergunta">
          {PASSOS[passo - 1].pergunta}
        </h1>

        <ol className="passos" aria-label="Passos">
          {PASSOS.map((p, i) => {
            const n = i + 1;
            const estado = n < passo ? "feito" : n === passo ? "atual" : "depois";
            const conteudo = (
              <>
                <span className="passos__numero" aria-hidden="true">
                  {estado === "feito" ? <Check size={14} strokeWidth={2.5} /> : n}
                </span>
                <span className="passos__nome">{p.curto}</span>
              </>
            );
            return (
              <li key={n} className={`passos__item passos__item--${estado}`} aria-current={estado === "atual" ? "step" : undefined}>
                {estado === "feito" ? (
                  <button type="button" className="passos__voltar" onClick={() => irPara(n)}>
                    {conteudo}
                  </button>
                ) : (
                  <span className="passos__voltar">{conteudo}</span>
                )}
              </li>
            );
          })}
        </ol>

        <section className="resumo" aria-label="Suas escolhas">
          <h2 className="resumo__titulo">Suas escolhas</h2>
          {resumoPreenchido.length ? (
            <dl className="resumo__lista">
              {resumoPreenchido.map(([k, v]) => (
                <div key={k} className="resumo__linha">
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="resumo__vazio">Aparecem aqui conforme você escolhe.</p>
          )}
        </section>

        <BarraProgresso passo={passo} total={3} />
      </aside>

      <div className="onb__area">
        <main className="onb__opcoes">
          {passo === 1 && (
            <>
              <fieldset className="grupo">
                <legend className="grupo__titulo">Faixa etária</legend>
                <div className="grupo__opcoes" role="radiogroup" aria-label="Faixa etária">
                  {FAIXAS.map(([v, r]) => (
                    <OpcaoUnica key={v} nome="faixa" marcado={faixa === v} onEscolher={() => setFaixa(v)}>
                      {r}
                    </OpcaoUnica>
                  ))}
                </div>
              </fieldset>
              <fieldset className="grupo">
                <legend className="grupo__titulo">
                  Gênero <span className="grupo__opcional">opcional</span>
                </legend>
                <div className="grupo__opcoes" role="radiogroup" aria-label="Gênero">
                  {GENEROS.map(([v, r]) => (
                    <OpcaoUnica key={v} nome="genero" marcado={genero === v} onEscolher={() => setGenero(v)}>
                      {r}
                    </OpcaoUnica>
                  ))}
                </div>
              </fieldset>
              <p className="nota">Anônimo. Usado só para recomendar ofertas.</p>
            </>
          )}

          {passo !== 1 && carga.estado === "carregando" && <p className="nota">Carregando…</p>}
          {passo !== 1 && carga.estado === "erro" && (
            <Aviso tipo="erro">
              <p>Não deu para carregar as opções.</p>
              <Botao variante="texto" onClick={() => setTentativa((t) => t + 1)}>
                Tentar de novo
              </Botao>
            </Aviso>
          )}

          {passo === 2 && carga.estado === "ok" && (
            <>
              <fieldset className="grupo">
                <legend className="grupo__titulo">
                  Categorias <span className="grupo__opcional">até 3</span>
                </legend>
                <div className="grade-categorias">
                  {carga.categorias.map((c) => (
                    <OpcaoVarias
                      key={c.slug}
                      className="ladrilho"
                      marcado={categorias.includes(c.slug)}
                      recusado={recusado === c.slug}
                      onAlternar={() => alternar(categorias, setCategorias, c.slug)}
                    >
                      <IconeCategoria icone={c.icone} />
                      <span className="ladrilho__nome">{c.nome}</span>
                    </OpcaoVarias>
                  ))}
                </div>
              </fieldset>
              <CampoTags
                rotulo="Algo específico?"
                dica="Opcional. Enter ou vírgula separa."
                placeholder="PS5, Dixit, air fryer..."
                valores={interesses}
                onMudar={setInteresses}
              />
            </>
          )}

          {passo === 3 && carga.estado === "ok" && (
            <fieldset className="grupo">
              <legend className="grupo__titulo">
                Aparecem primeiro no empate <span className="grupo__opcional">até 3</span>
              </legend>
              <div className="lojas__topo">
                <label className="busca-loja">
                  <Search size={18} strokeWidth={1.75} aria-hidden="true" />
                  <input
                    type="search"
                    placeholder="Buscar loja"
                    aria-label="Buscar loja"
                    value={filtro}
                    onChange={(e) => setFiltro(e.target.value)}
                  />
                </label>
                <OpcaoVarias
                  className="loja loja--nenhuma"
                  marcado={lojas.length === 0}
                  onAlternar={() => {
                    setLojas([]);
                    setLimite(false);
                  }}
                >
                  <span className="loja__nome">Não tenho preferência</span>
                </OpcaoVarias>
              </div>
              <div className="grade-lojas">
                {lojasVisiveis.map((l) => (
                  <OpcaoVarias
                    key={l.slug}
                    className="loja"
                    marcado={lojas.includes(l.slug)}
                    recusado={recusado === l.slug}
                    onAlternar={() => alternar(lojas, setLojas, l.slug)}
                  >
                    <IconeLoja slug={l.slug} nome={l.nome} />
                    <span className="loja__nome">{l.nome}</span>
                  </OpcaoVarias>
                ))}
              </div>
              {!lojasVisiveis.length && <p className="nota">Nenhuma loja com “{filtro.trim()}”.</p>}
            </fieldset>
          )}
        </main>

        <footer className="acoes">
          <div className="acoes__msg">
            <div role="status" className="acoes__status">
              {limite && (
                <>
                  <Info size={18} strokeWidth={1.75} aria-hidden="true" />
                  Máximo 3. Desmarque uma para trocar.
                </>
              )}
              {!limite && passo === 1 && !faixa && "Escolha a faixa etária"}
            </div>
            {erroSalvar && (
              <div role="alert" className="acoes__erro">
                <CircleAlert size={18} strokeWidth={1.75} aria-hidden="true" />
                Não deu para salvar. Suas escolhas continuam aqui.
              </div>
            )}
          </div>
          <div className="acoes__botoes">
            {passo > 1 && (
              <Botao variante="secundario" onClick={() => irPara(passo - 1)}>
                <ArrowLeft size={18} strokeWidth={1.75} aria-hidden="true" />
                Voltar
              </Botao>
            )}
            {passo < 3 ? (
              <Botao onClick={() => irPara(passo + 1)} disabled={(passo === 1 && !faixa) || (passo > 1 && !opcoesProntas)}>
                Avançar
                <ArrowRight size={18} strokeWidth={1.75} aria-hidden="true" />
              </Botao>
            ) : (
              <Botao onClick={concluir} disabled={salvando || !opcoesProntas}>
                {salvando ? "Salvando…" : erroSalvar ? "Tentar de novo" : "Concluir"}
              </Botao>
            )}
          </div>
        </footer>
      </div>
    </div>
  );
}

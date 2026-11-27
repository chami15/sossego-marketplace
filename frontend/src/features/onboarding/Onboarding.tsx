import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, type Categoria, type FaixaEtaria, type Genero, type Loja, type PerfilEntrada } from "../../api/cliente";
import { Aviso } from "../../components/Aviso";
import { BarraProgresso } from "../../components/BarraProgresso";
import { Botao } from "../../components/Botao";
import { CampoTags } from "../../components/CampoTags";
import { Chip } from "../../components/Chip";
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

type Carga = { estado: "carregando" } | { estado: "erro" } | { estado: "ok"; categorias: Categoria[]; lojas: Loja[] };

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

  const [limite, setLimite] = useState<"categorias" | "lojas" | null>(null);
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

  // Leitor de tela e teclado começam pela pergunta nova.
  useEffect(() => {
    titulo.current?.focus();
  }, [passo]);

  function alternar(lista: string[], setLista: (v: string[]) => void, slug: string, qual: "categorias" | "lojas") {
    if (lista.includes(slug)) {
      setLista(lista.filter((s) => s !== slug));
      setLimite(null);
    } else if (lista.length >= MAX) {
      setLimite(qual); // a mais antiga não sai sozinha
    } else {
      setLista([...lista, slug]);
      setLimite(null);
    }
  }

  function irPara(n: number) {
    setLimite(null);
    setErroSalvar(false);
    setPasso(n);
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

  return (
    <div className="onb">
      <BarraProgresso passo={passo} total={3} />
      <main className="onb__corpo">
        <p className="onb__passo">
          <span className="onb__marca">Sossego</span> · {passo} de 3
        </p>

        {passo === 1 && (
          <section aria-labelledby="pergunta">
            <h1 id="pergunta" ref={titulo} tabIndex={-1} className="onb__pergunta">
              Sobre você
            </h1>
            <fieldset className="onb__grupo">
              <legend className="onb__legenda">Faixa etária</legend>
              <div className="onb__chips">
                {FAIXAS.map(([v, r]) => (
                  <Chip key={v} selecionado={faixa === v} onAlternar={() => setFaixa(faixa === v ? null : v)}>
                    {r}
                  </Chip>
                ))}
              </div>
            </fieldset>
            <fieldset className="onb__grupo">
              <legend className="onb__legenda">
                Gênero <span className="onb__opcional">(opcional)</span>
              </legend>
              <div className="onb__chips">
                {GENEROS.map(([v, r]) => (
                  <Chip key={v} selecionado={genero === v} onAlternar={() => setGenero(genero === v ? null : v)}>
                    {r}
                  </Chip>
                ))}
              </div>
            </fieldset>
            <p className="onb__lgpd">
              Faixa etária e gênero são anônimos e servem só para recomendar ofertas. Não pedimos nome, e-mail nem
              login.
            </p>
          </section>
        )}

        {passo !== 1 && carga.estado === "carregando" && <p className="onb__carregando">Carregando…</p>}
        {passo !== 1 && carga.estado === "erro" && (
          <Aviso tipo="erro">
            <p>Não conseguimos carregar as opções. Confira se a API está no ar.</p>
            <Botao variante="texto" onClick={() => setTentativa((t) => t + 1)}>
              Tentar de novo
            </Botao>
          </Aviso>
        )}

        {passo === 2 && carga.estado === "ok" && (
          <section aria-labelledby="pergunta">
            <h1 id="pergunta" ref={titulo} tabIndex={-1} className="onb__pergunta">
              O que você procura?
            </h1>
            <p className="onb__apoio" id="apoio-categorias">
              Escolha até 3 categorias.
            </p>
            <div className="onb__grade" role="group" aria-describedby="apoio-categorias">
              {carga.categorias.map((c) => {
                const sel = categorias.includes(c.slug);
                return (
                  <button
                    key={c.slug}
                    type="button"
                    className="ladrilho"
                    aria-pressed={sel}
                    onClick={() => alternar(categorias, setCategorias, c.slug, "categorias")}
                  >
                    <span className="ladrilho__marca" aria-hidden="true">
                      {sel ? "✓" : ""}
                    </span>
                    <IconeCategoria icone={c.icone} />
                    <span>{c.nome}</span>
                  </button>
                );
              })}
            </div>
            <div className="onb__aviso-limite">
              {limite === "categorias" && (
                <Aviso tipo="info">Máximo 3. Desmarque uma categoria para escolher outra.</Aviso>
              )}
            </div>
            <CampoTags
              rotulo="Tem algo específico em mente?"
              dica="Opcional. Separe os termos com Enter ou vírgula."
              placeholder="PS5, Dixit, air fryer..."
              valores={interesses}
              onMudar={setInteresses}
            />
          </section>
        )}

        {passo === 3 && carga.estado === "ok" && (
          <section aria-labelledby="pergunta">
            <h1 id="pergunta" ref={titulo} tabIndex={-1} className="onb__pergunta">
              Lojas de confiança
            </h1>
            <p className="onb__apoio" id="apoio-lojas">
              A gente compara todas; estas aparecem primeiro quando o preço empatar. Até 3.
            </p>
            <div className="onb__aviso-limite">
              {limite === "lojas" && <Aviso tipo="info">Máximo 3. Desmarque uma loja para escolher outra.</Aviso>}
            </div>
            <button
              type="button"
              className="linha-loja linha-loja--nenhuma"
              aria-pressed={lojas.length === 0}
              onClick={() => {
                setLojas([]);
                setLimite(null);
              }}
            >
              <span className="linha-loja__nome">Não tenho preferência</span>
              <span className="linha-loja__marca" aria-hidden="true">
                {lojas.length === 0 ? "✓" : ""}
              </span>
            </button>
            <div className="onb__lojas" role="group" aria-describedby="apoio-lojas">
              {carga.lojas.map((l) => {
                const sel = lojas.includes(l.slug);
                return (
                  <button
                    key={l.slug}
                    type="button"
                    className="linha-loja"
                    aria-pressed={sel}
                    onClick={() => alternar(lojas, setLojas, l.slug, "lojas")}
                  >
                    <IconeLoja nome={l.nome} icone={l.icone} />
                    <span className="linha-loja__nome">{l.nome}</span>
                    <span className="linha-loja__marca" aria-hidden="true">
                      {sel ? "✓" : ""}
                    </span>
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {erroSalvar && (
          <div className="onb__erro">
            <Aviso tipo="erro">
              <p>
                <strong>Não conseguimos salvar suas preferências.</strong> Nada se perdeu: suas escolhas continuam
                aqui. Tente de novo em instantes.
              </p>
            </Aviso>
          </div>
        )}
      </main>

      <footer className="onb__rodape">
        <div className="onb__acoes">
          {passo > 1 ? (
            <Botao variante="secundario" onClick={() => irPara(passo - 1)}>
              Voltar
            </Botao>
          ) : (
            <span />
          )}
          <div className="onb__avancar">
            {passo === 1 && !faixa && <span className="onb__dica">Escolha a faixa etária para avançar.</span>}
            {passo < 3 ? (
              <Botao onClick={() => irPara(passo + 1)} disabled={passo === 1 && !faixa}>
                Avançar
              </Botao>
            ) : (
              <Botao onClick={concluir} disabled={salvando || carga.estado !== "ok"}>
                {salvando ? "Salvando…" : erroSalvar ? "Tentar de novo" : "Concluir"}
              </Botao>
            )}
          </div>
        </div>
      </footer>
    </div>
  );
}

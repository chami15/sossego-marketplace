import { ExternalLink, Eye } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";

import { api, type Card, type Historico, type Oferta, type Periodo, type Produto as DadosProduto } from "../../api/cliente";
import { Aviso } from "../../components/Aviso";
import { CardProduto, PrecoGrande } from "../../components/CardProduto";
import { ImagemProduto } from "../../components/ImagemProduto";
import { IconeCategoria, iconeDoSlug } from "../../components/IconeCategoria";
import { IconeLoja } from "../../components/IconeLoja";
import { OpcaoUnica } from "../../components/Escolha";
import { Rodape, Topo } from "../../components/Topo";
import { centavos, dataCurta, deNumeroBR, numeroBR, reais } from "../../formato";
import { useVigias } from "../../vigias";
import { Calculadora } from "./Calculadora";
import { GraficoPreco } from "./GraficoPreco";
import "./produto.css";

const PERIODOS: [Periodo, string][] = [
  ["24h", "24h"],
  ["7d", "7 dias"],
  ["30d", "30 dias"],
  ["tudo", "Tudo"],
];

// Custo efetivo de uma oferta para ordenar a tabela: o menor entre Pix e
// cartão, mais o frete. Em centavos (BigInt): dinheiro nunca é float.
// (A calculadora ao lado diz se o parcelado sem juros vale mais que o Pix.)
// O preço mostrado (destaque e botão) é o efetivo SEM frete; o frete aparece
// explícito embaixo. Só a ordenação usa o custo com frete.
const precoEfetivo = (o: Oferta) => (o.preco_pix && centavos(o.preco_pix) < centavos(o.preco) ? o.preco_pix : o.preco);

function custo(o: Oferta): bigint {
  return centavos(precoEfetivo(o)) + (o.frete ? centavos(o.frete) : 0n);
}

function linhaFrete(o: Oferta): string | null {
  if (o.frete === null) return null;
  return centavos(o.frete) === 0n ? "Frete grátis" : `+ ${reais(o.frete)} de frete`;
}

const viva = (o: Oferta) => !o.desatualizada && o.em_estoque !== false;

function parcelas(o: Oferta): string | null {
  if (o.parcelas_sem_juros && o.parcelas_sem_juros > 1) return `${o.parcelas_sem_juros}x sem juros`;
  if (o.parcelas_max && o.parcela_valor) return `${o.parcelas_max}x de ${reais(o.parcela_valor)}`;
  return null;
}

function Galeria({ imagens, categoria, titulo }: { imagens: string[]; categoria: string | null; titulo: string }) {
  const [atual, setAtual] = useState(0);
  return (
    <div className="galeria">
      <div className="galeria__principal">
        {imagens.length ? (
          <ImagemProduto src={imagens[atual]} alt={titulo} />
        ) : (
          <IconeCategoria icone={iconeDoSlug(categoria)} tamanho={72} />
        )}
      </div>
      {imagens.length > 1 && (
        <div className="galeria__miniaturas">
          {imagens.map((src, i) => (
            <button
              key={src}
              type="button"
              className={`galeria__mini ${i === atual ? "galeria__mini--atual" : ""}`}
              aria-label={`Imagem ${i + 1} de ${imagens.length}`}
              aria-pressed={i === atual}
              onClick={() => setAtual(i)}
            >
              <img src={src} alt="" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function FicarDeOlho({ produto, titulo }: { produto: number; titulo: string }) {
  const v = useVigias();
  const inicial = v.precoAlvo(produto);
  const [alvo, setAlvo] = useState(inicial ? numeroBR(inicial) : "");
  const [salvo, setSalvo] = useState<string | null>(null);
  if (!v.disponivel) return null;
  const ligado = v.vigiado(produto);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    const preco = deNumeroBR(alvo);
    await v.definir(produto, preco);
    setSalvo(preco ? `Avisamos quando ficar abaixo de ${reais(preco)}.` : "Vigiando. Aparece em De olho na página inicial.");
  }

  return (
    <form className="olho" onSubmit={enviar}>
      <label className="olho__alvo">
        <span>Preço-alvo (opcional)</span>
        <input inputMode="decimal" placeholder="R$" value={alvo} onChange={(e) => setAlvo(e.target.value)} />
      </label>
      <button type="submit" className="botao botao--primario">
        <Eye size={20} strokeWidth={1.75} aria-hidden="true" />
        {ligado ? "Atualizar" : "Ficar de olho"}
      </button>
      {ligado && (
        <button
          type="button"
          className="botao botao--texto"
          onClick={async () => {
            await v.alternar(produto);
            setSalvo(null);
          }}
        >
          Parar de vigiar
        </button>
      )}
      <p className="olho__status" role="status">
        {salvo ?? (ligado ? `Você está de olho em ${titulo}.` : "")}
      </p>
    </form>
  );
}

export function Produto() {
  const id = Number(useParams().id);
  const [p, setP] = useState<DadosProduto | null | "erro">(null);
  const [periodo, setPeriodo] = useState<Periodo>("30d");
  const [hist, setHist] = useState<Historico | null>(null);
  const [parecidos, setParecidos] = useState<Card[]>([]);
  const [escolha, setEscolha] = useState<Record<string, string>>({});

  useEffect(() => {
    setP(null);
    setEscolha({});
    window.scrollTo(0, 0);
    api.produto(id).then(setP).catch(() => setP("erro"));
    api.parecidos(id).then(setParecidos).catch(() => setParecidos([]));
  }, [id]);

  useEffect(() => {
    setHist(null);
    api.historico(id, periodo).then(setHist).catch(() => setHist(null));
  }, [id, periodo]);

  const dados = p && p !== "erro" ? p : null;

  // Seletor de variação: só as chaves em que as ofertas diferem.
  const variacoes = useMemo(() => {
    const m = new Map<string, Set<string>>();
    dados?.ofertas.forEach((o) => Object.entries(o.variacao ?? {}).forEach(([k, v]) => m.set(k, (m.get(k) ?? new Set()).add(v))));
    return [...m].filter(([, vs]) => vs.size > 1).map(([k, vs]) => [k, [...vs].sort()] as const);
  }, [dados]);

  const ofertas = useMemo(() => {
    const filtradas = (dados?.ofertas ?? []).filter((o) =>
      Object.entries(escolha).every(([k, v]) => (o.variacao ?? {})[k] === v),
    );
    // Vivas primeiro, pelo custo efetivo; depois as sem estoque ou antigas.
    return filtradas.sort((a, b) => Number(viva(b)) - Number(viva(a)) || (custo(a) < custo(b) ? -1 : custo(a) > custo(b) ? 1 : 0));
  }, [dados, escolha]);

  const nomes = useMemo(() => Object.fromEntries((dados?.ofertas ?? []).map((o) => [o.loja, o.loja_nome])), [dados]);

  if (p === "erro")
    return (
      <div className="pagina">
        <Topo />
        <main className="produto">
          <Aviso tipo="erro">
            <p>Produto não encontrado.</p>
          </Aviso>
        </main>
        <Rodape />
      </div>
    );
  if (!dados)
    return (
      <div className="pagina">
        <Topo />
        <main className="produto">
          <p>Carregando…</p>
        </main>
      </div>
    );

  const melhor = ofertas.find(viva) ?? null;
  // A galeria segue a variação escolhida e começa pela melhor oferta.
  const imagens = [...new Set(ofertas.map((o) => o.imagem_local).filter((x): x is string => Boolean(x)))];
  const especificacoes = Object.entries(dados.especificacoes ?? {});
  // Coluna que só teria "—" não aparece (a tabela cabe sem rolar).
  const temPix = ofertas.some((o) => o.preco_pix && o.preco_pix !== o.preco);
  const temParcelas = ofertas.some((o) => parcelas(o));
  const temFrete = ofertas.some((o) => o.frete !== null);

  return (
    <div className="pagina">
      <Topo />
      <main className="produto">
        <Galeria key={imagens.join()} imagens={imagens} categoria={dados.categoria} titulo={dados.titulo} />

        <div className="produto__centro">
          {dados.marca && <p className="produto__marca">{dados.marca}</p>}
          <h1 className="produto__titulo">{dados.titulo}</h1>

          {variacoes.map(([chave, valores]) => (
            <fieldset key={chave} className="variacao">
              <legend>{chave[0].toUpperCase() + chave.slice(1)}</legend>
              <div className="variacao__opcoes" role="radiogroup" aria-label={chave}>
                <OpcaoUnica nome={`var-${chave}`} marcado={!escolha[chave]} onEscolher={() => setEscolha(({ [chave]: _, ...r }) => r)}>
                  Todas
                </OpcaoUnica>
                {valores.map((v) => (
                  <OpcaoUnica key={v} nome={`var-${chave}`} marcado={escolha[chave] === v} onEscolher={() => setEscolha({ ...escolha, [chave]: v })}>
                    {v}
                  </OpcaoUnica>
                ))}
              </div>
            </fieldset>
          ))}

          {melhor ? (
            <section className="melhor" aria-labelledby="melhor-rotulo">
              <p id="melhor-rotulo" className="melhor__rotulo">
                Melhor oferta agora
              </p>
              <div className="melhor__linha">
                <PrecoGrande valor={precoEfetivo(melhor)} classe="melhor__preco" />
                <div className="melhor__detalhe">
                  {melhor.preco_pix && centavos(melhor.preco_pix) < centavos(melhor.preco) && (
                    <p>no Pix · {reais(melhor.preco)} no cartão</p>
                  )}
                  {parcelas(melhor) && <p>{parcelas(melhor)}</p>}
                  {linhaFrete(melhor) && <p>{linhaFrete(melhor)}</p>}
                  <p className="melhor__loja">
                    <IconeLoja slug={melhor.loja} nome={melhor.loja_nome} tamanho={20} />
                    {melhor.loja_nome}
                  </p>
                </div>
              </div>
              <a className="botao botao--primario melhor__comprar" href={melhor.url} target="_blank" rel="noopener noreferrer">
                Comprar na {melhor.loja_nome} por {reais(precoEfetivo(melhor))}
                <ExternalLink size={18} strokeWidth={1.75} aria-hidden="true" />
              </a>
            </section>
          ) : (
            <Aviso tipo="info">
              <p>Nenhuma loja com este produto em estoque nas últimas 48 h.</p>
            </Aviso>
          )}

          <section aria-labelledby="ofertas-titulo">
            <h2 id="ofertas-titulo" className="produto__secao">
              Ofertas por loja <span className="produto__conta">{ofertas.length}</span>
            </h2>
            <div className="tabela-rolagem">
              <table className="ofertas">
                <thead>
                  <tr>
                    <th scope="col">Loja</th>
                    <th scope="col">Preço</th>
                    {temPix && <th scope="col">Pix</th>}
                    {temParcelas && <th scope="col">Parcelas</th>}
                    {temFrete && <th scope="col">Frete</th>}
                    <th scope="col">
                      <span className="so-leitor">Ação</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {ofertas.map((o) => (
                    <tr key={o.anuncio_id} className={o === melhor ? "ofertas__melhor" : viva(o) ? "" : "ofertas__velha"}>
                      <th scope="row">
                        <span className="ofertas__loja">
                          <IconeLoja slug={o.loja} nome={o.loja_nome} tamanho={24} />
                          <span>
                            {o.loja_nome}
                            {o.vendedor && <span className="ofertas__vendedor">Vendido por {o.vendedor}</span>}
                            {!viva(o) && (
                              <span className="ofertas__vendedor">
                                {o.em_estoque === false ? "sem estoque" : `visto em ${dataCurta(o.ultima_coleta_em)}`}
                              </span>
                            )}
                          </span>
                        </span>
                      </th>
                      <td className="ofertas__preco" data-rotulo="Preço">{reais(o.preco)}</td>
                      {temPix && <td className="ofertas__pix" data-rotulo="Pix">{o.preco_pix && o.preco_pix !== o.preco ? reais(o.preco_pix) : "—"}</td>}
                      {temParcelas && <td data-rotulo="Parcelas">{parcelas(o) ?? "—"}</td>}
                      {temFrete && <td data-rotulo="Frete">{o.frete === null ? "—" : o.frete === "0.00" ? "grátis" : reais(o.frete)}</td>}
                      <td className="ofertas__acao">
                        <a className="botao botao--secundario ofertas__ir" href={o.url} target="_blank" rel="noopener noreferrer">
                          Ir para a loja
                          <ExternalLink size={16} strokeWidth={1.75} aria-hidden="true" />
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Vendedor já está na tabela; a seção só aparece com descrição ou especificações. */}
          {(dados.descricao || especificacoes.length > 0) && (
            <section aria-labelledby="sobre-titulo" className="sobre">
              <h2 id="sobre-titulo" className="produto__secao">
                Sobre o produto
              </h2>
              {dados.descricao && <p className="sobre__texto">{dados.descricao}</p>}
              {especificacoes.length > 0 && (
                <dl className="sobre__specs">
                  {especificacoes.map(([k, v]) => (
                    <div key={k}>
                      <dt>{k}</dt>
                      <dd>{v}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </section>
          )}
        </div>

        <aside className="lateral" aria-label="Histórico de preço e pagamento">
          <section aria-labelledby="hist-titulo">
            <h2 id="hist-titulo" className="lateral__titulo">
              Preço no tempo
            </h2>
            <div className="periodos" role="radiogroup" aria-label="Período">
              {PERIODOS.map(([v, r]) => (
                <OpcaoUnica key={v} nome="periodo" marcado={periodo === v} onEscolher={() => setPeriodo(v)}>
                  {r}
                </OpcaoUnica>
              ))}
            </div>
            {hist ? <GraficoPreco h={hist} nomes={nomes} /> : <div className="grafico grafico--carregando" />}
            {dados.menor_visto && (
              <p className="lateral__menor">
                Menor preço que vimos: <strong>{reais(dados.menor_visto.preco)}</strong> em {dataCurta(dados.menor_visto.em)}
              </p>
            )}
            <FicarDeOlho produto={dados.id} titulo={dados.titulo} />
          </section>
          {melhor && (
            <Calculadora
              key={melhor.anuncio_id}
              avista={melhor.preco_pix ?? melhor.preco}
              cartao={melhor.preco}
              parcelas={melhor.parcelas_sem_juros ?? 1}
            />
          )}
        </aside>
      </main>

      {parecidos.length > 0 && (
        <section className="parecidos" aria-labelledby="parecidos-titulo">
          <h2 id="parecidos-titulo" className="produto__secao">
            Você também pode gostar
          </h2>
          <div className="grade-cards">
            {parecidos.slice(0, 6).map((c) => (
              <CardProduto key={c.id} card={c} />
            ))}
          </div>
        </section>
      )}
      <Rodape />
    </div>
  );
}

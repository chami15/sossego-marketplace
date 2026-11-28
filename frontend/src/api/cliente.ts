// Contrato de backend/api/modelos.py. A API só lê o banco; nunca chama loja.

export type FaixaEtaria = "ate-17" | "18-24" | "25-34" | "35-44" | "45-59" | "60+";
export type Genero = "feminino" | "masculino" | "outro" | "prefiro-nao-dizer";

export interface Loja {
  slug: string;
  nome: string;
  dominio: string;
  icone: string | null;
  coleta_ativa: boolean;
}

export interface Categoria {
  slug: string;
  nome: string;
  icone: string;
}

export interface PerfilEntrada {
  faixa_etaria: FaixaEtaria;
  genero: Genero | null;
  categorias: string[];
  lojas: string[];
  interesses: string[];
}

export interface Perfil extends PerfilEntrada {
  id: string;
}

// Dinheiro chega como string decimal ("4289.00"): nunca vira number aqui.
export interface Card {
  id: number;
  titulo: string;
  imagem: string | null;
  imagem_local: string | null; // WebP baixado pelo worker; o CDN da loja nunca é pedido pela tela
  categoria: string | null;
  menor_preco: string;
  loja: string;
  loja_nome: string;
  loja_icone: string | null;
  url: string;
  menor_pix: string | null;
  outras_lojas: number;
  outras_a_partir: string | null;
  variacao_pct: string | null;
  variacao_desde: string | null;
  menor_visto: string | null;
  menor_visto_em: string | null;
}

export interface Recomendacao extends Card {
  porque: string;
}

export interface Inicio {
  de_olho: Card[];
  pra_voce: Recomendacao[];
  caiu_de_preco: Card[];
  categorias: Categoria[];
}

export type Ordem = "relevancia" | "preco" | "pix" | "queda";

export interface ResultadoBusca {
  q: string;
  categoria: string | null;
  ordem: Ordem;
  total: number;
  resultados: Card[];
}

export interface PedidoBusca {
  q?: string;
  categoria?: string;
  ordem?: Ordem;
  lojas?: string[];
  preco_min?: string;
  preco_max?: string;
  perfil?: string | null;
}

export interface SaudeLoja {
  slug: string;
  nome: string;
  situacao: string;
  texto: string;
  ultima_ok: string | null;
}

export interface Vigia {
  produto_id: number;
  preco_alvo: string | null;
}

export interface Oferta {
  anuncio_id: number;
  loja: string;
  loja_nome: string;
  url: string;
  titulo_original: string;
  vendedor: string | null;
  variacao: Record<string, string>;
  imagem: string | null;
  imagem_local: string | null;
  preco_de: string | null;
  preco: string;
  preco_pix: string | null;
  parcelas_max: number | null;
  parcela_valor: string | null;
  parcelas_sem_juros: number | null;
  frete: string | null;
  em_estoque: boolean | null;
  coletado_em: string;
  ultima_coleta_em: string;
  desatualizada: boolean;
}

export interface PrecoVisto {
  preco: string;
  em: string;
  loja: string;
}

export interface Produto {
  id: number;
  titulo: string;
  marca: string | null;
  modelo: string | null;
  gtin: string | null;
  imagem: string | null;
  descricao: string | null;
  especificacoes: Record<string, string>;
  categoria: string | null;
  a_confirmar: boolean;
  ofertas: Oferta[];
  menor_visto: PrecoVisto | null;
}

export type Periodo = "24h" | "7d" | "30d" | "tudo";

export interface Ponto {
  em: string;
  preco: string;
  preco_pix?: string | null;
}

export interface Serie {
  anuncio_id: number;
  loja: string;
  titulo: string;
  pontos: Ponto[];
}

export interface Historico {
  produto_id: number;
  periodo: Periodo;
  desde: string | null;
  series: Serie[];
  menor_geral: Ponto[];
  menor_visto: PrecoVisto | null;
}

export interface SimulacaoEntrada {
  preco_avista: string;
  preco_cartao: string;
  parcelas: number;
  valor_parcela?: string | null;
  pct_cdi?: string;
  cashback_pct?: string;
}

export interface OpcaoPagamento {
  tipo: "pix" | "parcelado";
  parcelas: number | null;
  valor_parcela: string | null;
  total: string;
  valor_presente: string;
  cashback: string;
  custo_efetivo: string;
  desconto_equilibrio_pct: string | null;
  juros_mensal_pct: string | null;
}

export interface Simulacao {
  recomendacao: string;
  melhor: OpcaoPagamento;
  opcoes: OpcaoPagamento[];
  desconto_pix_pct: string;
  economia: string;
  rendimento_fonte: "informado" | "cdi_bcb";
  cdi_anual_pct: string | null;
  cdi_data: string | null;
}

export class ErroApi extends Error {
  constructor(public status: number, mensagem: string) {
    super(mensagem);
  }
}

async function pedir<T>(caminho: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`/api/v1${caminho}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ErroApi(0, "sem conexão com a API");
  }
  if (!r.ok) {
    const corpo = await r.json().catch(() => null);
    throw new ErroApi(r.status, typeof corpo?.detail === "string" ? corpo.detail : `HTTP ${r.status}`);
  }
  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}

export const api = {
  lojas: () => pedir<Loja[]>("/lojas"),
  categorias: () => pedir<Categoria[]>("/categorias"),
  perfil: (id: string) => pedir<Perfil>(`/perfis/${id}`),
  criarPerfil: (p: PerfilEntrada) => pedir<Perfil>("/perfis", { method: "POST", body: JSON.stringify(p) }),
  salvarPerfil: (id: string, p: PerfilEntrada) =>
    pedir<Perfil>(`/perfis/${id}`, { method: "PUT", body: JSON.stringify(p) }),
  inicio: (perfil: string | null) => pedir<Inicio>(`/inicio${perfil ? `?perfil=${perfil}` : ""}`),
  busca: (b: PedidoBusca) => {
    const p = new URLSearchParams();
    if (b.q) p.set("q", b.q);
    if (b.categoria) p.set("categoria", b.categoria);
    if (b.ordem) p.set("ordem", b.ordem);
    b.lojas?.forEach((l) => p.append("loja", l));
    if (b.preco_min) p.set("preco_min", b.preco_min);
    if (b.preco_max) p.set("preco_max", b.preco_max);
    if (b.perfil) p.set("perfil", b.perfil);
    return pedir<ResultadoBusca>(`/busca?${p}`);
  },
  saude: () => pedir<{ lojas: SaudeLoja[] }>("/saude"),
  vigias: (perfil: string) => pedir<Vigia[]>(`/perfis/${perfil}/vigias`),
  vigiar: (perfil: string, produto: number, preco_alvo: string | null = null) =>
    pedir<void>(`/perfis/${perfil}/vigias/${produto}`, { method: "POST", body: JSON.stringify({ preco_alvo }) }),
  desvigiar: (perfil: string, produto: number) =>
    pedir<void>(`/perfis/${perfil}/vigias/${produto}`, { method: "DELETE" }),
  produto: (id: number) => pedir<Produto>(`/produtos/${id}`),
  historico: (id: number, periodo: Periodo) => pedir<Historico>(`/produtos/${id}/historico?periodo=${periodo}`),
  parecidos: (id: number) => pedir<Card[]>(`/produtos/${id}/parecidos`),
  simular: (e: SimulacaoEntrada) =>
    pedir<Simulacao>("/pagamento/simular", { method: "POST", body: JSON.stringify(e) }),
};

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
};

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
};

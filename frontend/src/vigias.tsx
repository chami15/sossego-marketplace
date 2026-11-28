import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { useLocation } from "react-router-dom";

import { api } from "./api/cliente";
import { perfilSalvo } from "./perfil";

// O que o perfil vigia, para o botão do card e da página de produto. Fonte da
// verdade é a API; aqui só fica a cópia da sessão para responder na hora.
interface Contexto {
  disponivel: boolean; // sem perfil não há onde guardar a vigia
  vigiado: (produto: number) => boolean;
  precoAlvo: (produto: number) => string | null;
  alternar: (produto: number) => Promise<void>;
  definir: (produto: number, precoAlvo: string | null) => Promise<void>;
}

const Ctx = createContext<Contexto | null>(null);

export function VigiasProvider({ children }: { children: ReactNode }) {
  useLocation(); // relê o perfil ao navegar: o onboarding cria o perfil sem recarregar a página
  const perfil = perfilSalvo();
  const [mapa, setMapa] = useState<Map<number, string | null>>(new Map());

  useEffect(() => {
    if (!perfil) return;
    api
      .vigias(perfil)
      .then((vs) => setMapa(new Map(vs.map((v) => [v.produto_id, v.preco_alvo]))))
      .catch(() => undefined);
  }, [perfil]);

  const definir = useCallback(
    async (produto: number, precoAlvo: string | null) => {
      if (!perfil) return;
      await api.vigiar(perfil, produto, precoAlvo);
      setMapa((m) => new Map(m).set(produto, precoAlvo));
    },
    [perfil],
  );

  const alternar = useCallback(
    async (produto: number) => {
      if (!perfil) return;
      if (mapa.has(produto)) {
        await api.desvigiar(perfil, produto);
        setMapa((m) => {
          const n = new Map(m);
          n.delete(produto);
          return n;
        });
      } else {
        await definir(produto, null);
      }
    },
    [perfil, mapa, definir],
  );

  const valor = useMemo<Contexto>(
    () => ({
      disponivel: Boolean(perfil),
      vigiado: (p) => mapa.has(p),
      precoAlvo: (p) => mapa.get(p) ?? null,
      alternar,
      definir,
    }),
    [perfil, mapa, alternar, definir],
  );
  return <Ctx.Provider value={valor}>{children}</Ctx.Provider>;
}

export function useVigias(): Contexto {
  const c = useContext(Ctx);
  if (!c) throw new Error("useVigias fora do VigiasProvider");
  return c;
}

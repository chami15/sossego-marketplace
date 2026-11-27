// Autocomplete da busca: o histórico fica só neste navegador.
const CHAVE = "sossego.buscas";
const MAX = 8;

export function buscasRecentes(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(CHAVE) ?? "[]");
    return Array.isArray(v) ? v.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function lembrarBusca(termo: string) {
  const t = termo.trim();
  if (!t) return;
  const lista = [t, ...buscasRecentes().filter((x) => x.toLowerCase() !== t.toLowerCase())].slice(0, MAX);
  try {
    localStorage.setItem(CHAVE, JSON.stringify(lista));
  } catch {
    /* sem storage, sem sugestão */
  }
}

// O perfil é anônimo: só o UUID fica no navegador; o resto, no banco.
const CHAVE = "sossego.perfil";

export function perfilSalvo(): string | null {
  try {
    return localStorage.getItem(CHAVE);
  } catch {
    return null; // navegação privada com storage bloqueado: refaz o onboarding
  }
}

export function guardarPerfil(id: string) {
  try {
    localStorage.setItem(CHAVE, id);
  } catch {
    /* sem storage, o perfil vale só nesta visita */
  }
}

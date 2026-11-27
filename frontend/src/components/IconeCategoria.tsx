import {
  BookOpen,
  Dices,
  Dumbbell,
  Footprints,
  Gamepad2,
  House,
  Laptop,
  Refrigerator,
  Shirt,
  SprayCan,
  ToyBrick,
  Tv,
  type LucideIcon,
} from "lucide-react";

// Chave = categoria.icone da migration 004. Todos os ícones do app vêm do Lucide.
const ICONES: Record<string, LucideIcon> = {
  geladeira: Refrigerator,
  tv: Tv,
  controle: Gamepad2,
  dado: Dices,
  notebook: Laptop,
  camiseta: Shirt,
  tenis: Footprints,
  frasco: SprayCan,
  casa: House,
  urso: ToyBrick,
  livro: BookOpen,
  bola: Dumbbell,
};

// slug da categoria → chave do ícone (mesma tabela da migration 004), para o card.
const DO_SLUG: Record<string, string> = {
  eletrodomesticos: "geladeira",
  eletronicos: "tv",
  games: "controle",
  "jogos-tabuleiro": "dado",
  informatica: "notebook",
  vestuario: "camiseta",
  calcados: "tenis",
  cosmeticos: "frasco",
  casa: "casa",
  brinquedos: "urso",
  livros: "livro",
  esporte: "bola",
};

export const iconeDoSlug = (slug: string | null) => DO_SLUG[slug ?? ""] ?? "casa";

export function IconeCategoria({ icone, tamanho = 24 }: { icone: string; tamanho?: number }) {
  const Icone = ICONES[icone] ?? House;
  return <Icone size={tamanho} strokeWidth={1.5} aria-hidden="true" />;
}

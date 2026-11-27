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

export function IconeCategoria({ icone, tamanho = 24 }: { icone: string; tamanho?: number }) {
  const Icone = ICONES[icone] ?? House;
  return <Icone size={tamanho} strokeWidth={1.5} aria-hidden="true" />;
}

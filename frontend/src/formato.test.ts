// npm run test:unit (node --test; o Node 24 roda TypeScript direto).
import assert from "node:assert/strict";
import { test } from "node:test";

import { centavos, deCentavos, partesReais, porcento, reais } from "./formato.ts";

const NBSP = " ";

test("reais: formato brasileiro, vírgula nos centavos e ponto no milhar", () => {
  assert.equal(reais("4289.00"), `R$${NBSP}4.289,00`);
  assert.equal(reais("1299.9"), `R$${NBSP}1.299,90`);
  assert.equal(reais("0.5"), `R$${NBSP}0,50`);
  assert.equal(reais("1234567.89"), `R$${NBSP}1.234.567,89`);
});

test("reais: string decimal não passa por float (sem 0,1 + 0,2)", () => {
  assert.equal(reais("90071992547409.93"), `R$${NBSP}90.071.992.547.409,93`);
});

test("regressão: centavos com ponto (R$ 4.289.00 no card da Fase 7)", () => {
  const p = partesReais("4289.00");
  assert.deepEqual([p.inteiro, p.centavos], ["4.289", "00"]);
  // O texto acessível (lido e copiado) é sempre o formato brasileiro completo.
  assert.equal(p.texto, `R$${NBSP}4.289,00`);
  assert.doesNotMatch(p.texto, /\d\.\d{2}$/);
});

test("porcento: vírgula decimal, sem sinal (a seta diz a direção)", () => {
  assert.equal(porcento("-14.3"), "14,3%");
  assert.equal(porcento("5.0"), "5%");
});

test("centavos: aritmética exata em BigInt, ida e volta", () => {
  assert.equal(centavos("4289.00"), 428900n);
  assert.equal(centavos("0.1") + centavos("0.2"), centavos("0.3"));
  assert.equal(centavos("19.9"), 1990n);
  assert.equal(deCentavos(428900n + 1990n), "4308.90");
  assert.equal(deCentavos(5n), "0.05");
});
import { expect, test, type Page } from "@playwright/test";

// Fase 8: página de produto com a API real no banco do e2e (db/semente_e2e.py).
async function comPerfil(page: Page) {
  const r = await page.request.post("/api/v1/perfis", {
    data: { faixa_etaria: "25-34", categorias: ["games"], lojas: [], interesses: [] },
  });
  const { id } = await r.json();
  await page.addInitScript((pid) => localStorage.setItem("sossego.perfil", pid), id);
  return id as string;
}

async function idDe(page: Page, q: string) {
  const r = await page.request.get(`/api/v1/busca?q=${encodeURIComponent(q)}`);
  return (await r.json()).resultados[0].id as number;
}

const cards = (p: Page) => p.locator(".grade-cards .card");

test("produto → Ir para a loja: ofertas por custo efetivo e a melhor no topo", async ({ page }) => {
  await comPerfil(page);
  await page.goto("/busca?q=mario%20kart");
  await cards(page).first().click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Jogo Mario Kart 8 Deluxe, Nintendo Switch");

  // Melhor: Kabum no Pix (284,90) vence a Amazon (319,00).
  const comprar = page.getByRole("link", { name: "Comprar na Kabum por R$ 284,90" });
  await expect(comprar).toHaveAttribute("href", "https://example.com/kabum/e2e-mk8");
  await expect(comprar).toHaveAttribute("target", "_blank");

  const linhas = page.locator("table.ofertas tbody tr");
  await expect(linhas).toHaveCount(2);
  await expect(linhas.nth(0)).toContainText("Kabum");
  await expect(linhas.nth(1)).toContainText("Amazon");
  const ir = linhas.nth(1).getByRole("link", { name: "Ir para a loja" });
  await expect(ir).toHaveAttribute("href", "https://example.com/amazon/e2e-mk8-a");
  await expect(ir).toHaveAttribute("rel", /noopener/);

  // A loja abre em nova aba (a página da loja de exemplo não carrega no e2e).
  const [aba] = await Promise.all([
    page.context().waitForEvent("page"),
    ir.click(),
  ]);
  expect(aba.url()).toContain("example.com/amazon/e2e-mk8-a");
  await aba.close();
});

test("frete entra no custo: PS5 da Kabum (frete grátis) antes da Amazon (+19,90)", async ({ page }) => {
  await comPerfil(page);
  await page.goto(`/produto/${await idDe(page, "console ps5")}`);
  await expect(page.getByRole("link", { name: /^Comprar na Kabum por R\$ 4\.289,00/ })).toBeVisible();
  const linhas = page.locator("table.ofertas tbody tr");
  await expect(linhas.nth(0)).toContainText("10x sem juros");
  await expect(linhas.nth(0)).toContainText("grátis");
  await expect(linhas.nth(1)).toContainText("R$ 19,90");
  await expect(page.getByText("vendido por KaBuM!")).toBeVisible();
});

test("variação: escolher a cor muda as ofertas mostradas", async ({ page }) => {
  await comPerfil(page);
  await page.goto(`/produto/${await idDe(page, "dualsense")}`);
  const linhas = page.locator("table.ofertas tbody tr");
  await expect(linhas).toHaveCount(2);
  await page.getByRole("radio", { name: "Preto" }).locator("xpath=..").click();
  await expect(linhas).toHaveCount(1);
  await expect(linhas.first()).toContainText("Ri Happy");
  await expect(page.getByRole("link", { name: /^Comprar na Ri Happy por R\$ 444,90/ })).toBeVisible(); // 429,90 + frete 15
});

test("gráfico: legenda por loja, período e a tabela com os pontos", async ({ page }) => {
  await comPerfil(page);
  await page.goto(`/produto/${await idDe(page, "console ps5")}`);
  const grafico = page.locator(".grafico");
  await expect(grafico.locator(".grafico__legenda")).toContainText("Kabum");
  await expect(grafico.locator(".grafico__legenda")).toContainText("Amazon");
  await expect(grafico.locator(".grafico__legenda")).toContainText("Menor preço geral");
  await page.getByText("Ver em tabela").click();
  await expect(grafico.locator("table tbody tr")).toHaveCount(5); // 3 da Kabum + 2 da Amazon em 30 dias

  // Mira: passar o mouse mostra data, loja e preço.
  const svg = grafico.locator(".grafico__area svg");
  const caixa = (await svg.boundingBox())!;
  await page.mouse.move(caixa.x + caixa.width - 2, caixa.y + caixa.height / 2); // ponta direita = coleta mais recente
  await expect(grafico.locator(".grafico__dica")).toContainText("R$ 4.289,00");

  await page.getByRole("radio", { name: "24h" }).locator("xpath=..").click();
  await expect(page.getByRole("radio", { name: "24h" })).toBeChecked();
  await expect(grafico.locator(".grafico__legenda")).toBeVisible();
  await expect(page.getByText(/Menor preço que vimos: R\$\s4\.289,00/)).toBeVisible();
});

test("um ponto só: sem gráfico inventado, com o aviso", async ({ page }) => {
  await comPerfil(page);
  await page.goto(`/produto/${await idDe(page, "cascadia")}`);
  await expect(page.getByText("Começamos a acompanhar hoje. Volte amanhã para ver a variação.")).toBeVisible();
});

test("ficar de olho com preço-alvo grava a vigia; o card mostra vigiando", async ({ page }) => {
  const pid = await comPerfil(page);
  const id = await idDe(page, "dixit");
  await page.goto(`/produto/${id}`);
  await page.getByLabel("Preço-alvo (opcional)").fill("150,00");
  await page.getByRole("button", { name: "Ficar de olho" }).click();
  await expect(page.getByRole("status").filter({ hasText: "abaixo de R$ 150,00" })).toBeVisible();
  const vigias = await (await page.request.get(`/api/v1/perfis/${pid}/vigias`)).json();
  expect(vigias).toEqual([{ produto_id: id, preco_alvo: "150.00" }]);

  await page.goto("/");
  const deOlho = page.locator("section", { has: page.getByRole("heading", { name: "De olho" }) });
  await expect(deOlho.locator(".card")).toHaveCount(1);
  await expect(deOlho.getByRole("button", { name: /^Parar de vigiar/ })).toHaveAttribute("aria-pressed", "true");
});

test("botão vigiar do card não abre o produto", async ({ page }) => {
  const pid = await comPerfil(page);
  await page.goto("/busca?q=ito");
  const card = cards(page).first();
  await card.hover();
  const botao = card.getByRole("button", { name: "Vigiar o preço de Ito" });
  await botao.click();
  await expect(page).toHaveURL(/\/busca\?q=ito$/);
  await expect(card.getByRole("button", { name: "Parar de vigiar Ito" })).toHaveAttribute("aria-pressed", "true");
  const vigias = await (await page.request.get(`/api/v1/perfis/${pid}/vigias`)).json();
  expect(vigias).toHaveLength(1);
});

test("calculadora: Pix × parcelado com o CDI do Banco Central", async ({ page }) => {
  await comPerfil(page);
  await page.goto(`/produto/${await idDe(page, "console ps5")}`);
  const calc = page.locator(".calc");
  await expect(calc.getByLabel("No cartão (R$)")).toHaveValue("4289,00");
  await expect(calc.locator(".calc__veredito")).not.toBeEmpty();
  await expect(calc).toContainText("CDI 13,65% a.a.");
  await calc.getByLabel("No Pix (R$)").fill("3900,00");
  await expect(calc.locator(".calc__opcao--melhor")).toContainText("Pix");
});

test("parecidos: produtos da mesma categoria, já com preço", async ({ page }) => {
  await comPerfil(page);
  await page.goto(`/produto/${await idDe(page, "dixit")}`);
  const sec = page.locator(".parecidos");
  await expect(sec.getByRole("heading", { name: "Você também pode gostar" })).toBeVisible();
  await expect(sec.locator(".card").first()).toContainText("R$");
});

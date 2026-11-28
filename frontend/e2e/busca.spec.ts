import { expect, test, type Page } from "@playwright/test";

// Banco do e2e semeado por backend/db/semente_e2e.py (anúncios fictícios).
async function comPerfil(page: Page) {
  const r = await page.request.post("/api/v1/perfis", {
    data: { faixa_etaria: "25-34", categorias: ["games", "jogos-tabuleiro"], lojas: [], interesses: ["dixit"] },
  });
  const { id } = await r.json();
  await page.addInitScript((pid) => localStorage.setItem("sossego.perfil", pid), id);
}

const cards = (p: Page) => p.locator(".grade-cards .card");

test("busca → card → produto: menor preço, lojas, Pix e variação real", async ({ page }) => {
  await comPerfil(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "O que você quer comprar hoje?" })).toBeVisible();

  await page.getByRole("combobox", { name: "O que você quer comprar hoje?" }).fill("mario kart");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/busca\?q=mario%20kart$/);
  await expect(page.getByRole("heading", { name: "“mario kart”" })).toBeVisible();
  await expect(page.getByText("1 produto")).toBeVisible();

  const card = cards(page).first();
  // Texto lido: formato brasileiro completo, vírgula nos centavos (regressão do "4.289.00").
  await expect(card.locator(".card__preco .so-leitor")).toHaveText("R$ 299,90"); // Kabum vence a Amazon
  await expect(card).toContainText("Pix R$ 284,90");
  await expect(card).toContainText("Kabum");
  await expect(card).toContainText("+1 loja a partir de R$ 319,00");
  await expect(card.locator(".selo--queda")).toContainText(/caiu\s*14,3%/); // seta + texto, não só cor

  await card.click(); // o card inteiro é o link
  await expect(page).toHaveURL(/\/produto\/\d+$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Mario Kart 8 Deluxe");
  await expect(page.getByRole("link", { name: "Ir para a loja" })).toHaveCount(2);
});

test("ordenar e filtrar ficam na URL e mudam o resultado", async ({ page }) => {
  await comPerfil(page);
  await page.goto("/busca?q=ps5");
  await expect(cards(page)).toHaveCount(2);

  await page.getByRole("radio", { name: "Menor preço" }).locator("xpath=..").click();
  await expect(page).toHaveURL(/ordem=preco/);
  await expect(cards(page).first()).toContainText("Controle");

  await page.getByLabel("Preço mínimo").fill("1.000");
  await page.getByRole("button", { name: "Aplicar" }).click();
  await expect(page).toHaveURL(/min=1000/);
  await expect(cards(page)).toHaveCount(1);
  await expect(cards(page).first()).toContainText("Console");

  await page.getByRole("button", { name: "Limpar filtros" }).click();
  await expect(cards(page)).toHaveCount(2);

  await page.getByLabel("Loja", { exact: true }).selectOption("amazon");
  await expect(cards(page)).toHaveCount(1);
  await expect(cards(page).first()).toContainText("Amazon");
});

test("home: seções com cards e chip de categoria abre a categoria", async ({ page }) => {
  await comPerfil(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Pra você" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "De olho" })).toBeVisible();
  // Produto não se repete entre seções (Pra você e Caiu de preço se sobrepõem na API).
  const links = await page.locator(".grade-cards .card__link").evaluateAll((as) => as.map((a) => a.getAttribute("href")));
  expect(links.length).toBeGreaterThan(0);
  expect(new Set(links).size).toBe(links.length);
  await page.getByRole("link", { name: "Jogos de tabuleiro", exact: true }).click();
  await expect(page).toHaveURL(/categoria=jogos-tabuleiro/);
  await expect(page.getByRole("heading", { name: "Jogos de tabuleiro" })).toBeVisible();
  await expect(cards(page)).toHaveCount(3); // Dixit, Ito e Cascadia
});

test("busca sem nada no histórico explica de onde vêm os preços", async ({ page }) => {
  await comPerfil(page);
  await page.goto("/busca?q=geladeira%20frost%20free");
  await expect(page.getByText("Nada no histórico para “geladeira frost free”.")).toBeVisible();
});

test("autocomplete: a busca feita volta como sugestão", async ({ page }) => {
  await comPerfil(page);
  await page.goto("/");
  await page.getByRole("combobox", { name: "O que você quer comprar hoje?" }).fill("dixit");
  await page.keyboard.press("Enter");
  await expect(cards(page)).toHaveCount(1);
  const sugestoes = await page.evaluate(() => JSON.parse(localStorage.getItem("sossego.buscas") ?? "[]"));
  expect(sugestoes).toEqual(["dixit"]);
  await expect(page.locator("datalist option[value='dixit']")).toHaveCount(1);
});

test("regressão: no celular a busca estourava a largura da tela", async ({ page }) => {
  await comPerfil(page);
  await page.setViewportSize({ width: 390, height: 844 });
  const ps5 = (await (await page.request.get("/api/v1/busca?q=console%20ps5")).json()).resultados[0].id;
  for (const url of ["/", "/busca?q=ps5", `/produto/${ps5}`]) {
    await page.goto(url);
    await expect(page.locator(".card, .melhor").first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth), url).toBeLessThanOrEqual(390);
  }
});

test("situação das lojas: sem estado é neutro (cinza); vermelho só para bloqueada ou atrasada", async ({ page }) => {
  await comPerfil(page);
  // O e2e não tem dados/coleta.sqlite3: todas as lojas vêm "sem_estado".
  await page.goto("/busca?q=ps5");
  const kabum = page.locator(".coletas__loja", { hasText: "Kabum" });
  await expect(kabum).toHaveClass(/coletas__loja--neutro/);
  await expect(kabum).toContainText("sem dados da coleta");
  await expect(page.locator(".coletas__loja--alerta")).toHaveCount(0);

  await page.route("**/api/v1/saude", (r) =>
    r.fulfill({ json: { lojas: [
      { slug: "kabum", nome: "Kabum", situacao: "bloqueio", texto: "x", ultima_ok: null },
      { slug: "ludopedia", nome: "Ludopedia", situacao: "atrasada", texto: "x", ultima_ok: null },
    ] } }));
  await page.reload();
  await expect(page.locator(".coletas__loja--alerta")).toHaveCount(2);
  await expect(page.locator(".coletas__loja", { hasText: "Kabum" })).toContainText("bloqueada");
});
import { expect, test, type Page } from "@playwright/test";

// Os controles são radio/checkbox nativos escondidos atrás do visual: a pessoa
// clica no rótulo (o que se vê); a conferência é pelo estado do controle.
const radio = (p: Page, nome: string) => p.getByRole("radio", { name: nome, exact: true });
const caixa = (p: Page, nome: string) => p.getByRole("checkbox", { name: nome, exact: true });
const clicar = (alvo: ReturnType<typeof radio>) => alvo.locator("xpath=..").click();

async function perfilNoBanco(page: Page) {
  const id = await page.evaluate(() => localStorage.getItem("sossego.perfil"));
  expect(id).toBeTruthy();
  const r = await page.request.get(`/api/v1/perfis/${id}`);
  expect(r.ok()).toBeTruthy();
  return r.json();
}

async function passo1(page: Page) {
  await page.goto("/");
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("heading", { name: "Sobre você" })).toBeVisible();
  const avancar = page.getByRole("button", { name: "Avançar" });
  await expect(avancar).toBeDisabled(); // gênero é opcional; faixa, não
  await expect(page.getByRole("status")).toHaveText("Escolha a faixa etária");
  await clicar(radio(page, "25–34"));
  await expect(radio(page, "25–34")).toBeChecked();
  await avancar.click();
}

test("onboarding completo grava o perfil anônimo com os limites de 3", async ({ page }) => {
  await passo1(page);

  await expect(page.getByRole("heading", { name: "O que você procura?" })).toBeVisible();
  for (const c of ["Games", "Jogos de tabuleiro", "Informática"]) await clicar(caixa(page, c));
  await clicar(caixa(page, "Livros"));
  await expect(page.getByRole("status")).toContainText("Máximo 3");
  await expect(caixa(page, "Livros")).not.toBeChecked();
  await expect(caixa(page, "Games")).toBeChecked(); // a mais antiga não sai sozinha
  await expect(page.getByRole("complementary")).toContainText("Games, Jogos de tabuleiro, Informática");

  const termos = page.getByLabel("Algo específico?");
  await termos.fill("PS5");
  await termos.press("Enter");
  await termos.fill("Dixit,air fryer,");
  await expect(page.getByRole("list", { name: "Termos adicionados" }).getByRole("listitem")).toHaveCount(3);
  await page.getByRole("button", { name: "Remover air fryer" }).click();
  await page.getByRole("button", { name: "Avançar" }).click();

  await expect(page.getByRole("heading", { name: "Lojas de confiança" })).toBeVisible();
  await expect(caixa(page, "Não tenho preferência")).toBeChecked();
  const busca = page.getByRole("searchbox", { name: "Buscar loja" });
  await busca.fill("ri h");
  await expect(page.locator(".grade-lojas input")).toHaveCount(1);
  await clicar(caixa(page, "Ri Happy"));
  await busca.fill("");
  for (const l of ["Kabum", "Ludopedia"]) await clicar(caixa(page, l));
  await expect(caixa(page, "Não tenho preferência")).not.toBeChecked();
  await clicar(caixa(page, "Amazon"));
  await expect(page.getByRole("status")).toContainText("Máximo 3");
  await page.getByRole("button", { name: "Concluir" }).click();

  await expect(page.getByRole("heading", { name: "Pronto. Suas preferências estão salvas." })).toBeVisible();
  // Nomes de exibição, nunca slugs (o hífen quebrava a linha no celular).
  const resumo = page.locator(".pronto__resumo");
  for (const n of ["Ri Happy", "Kabum", "Ludopedia", "Jogos de tabuleiro", "Informática"]) await expect(resumo).toContainText(n);
  await expect(resumo).not.toContainText("ri-happy");
  await expect(resumo).not.toContainText("jogos-tabuleiro");
  const p = await perfilNoBanco(page);
  expect(p).toMatchObject({ faixa_etaria: "25-34", genero: null, interesses: ["ps5", "dixit"] });
  // O banco devolve categorias e lojas na ordem dele; o que importa é o conjunto.
  expect([...p.categorias].sort()).toEqual(["games", "informatica", "jogos-tabuleiro"]);
  expect([...p.lojas].sort()).toEqual(["kabum", "ludopedia", "ri-happy"]);
});

test("refazer preferências volta com as escolhas e salva no mesmo perfil", async ({ page }) => {
  await passo1(page);
  await page.getByRole("button", { name: "Avançar" }).click();
  await clicar(caixa(page, "Kabum"));
  await page.getByRole("button", { name: "Concluir" }).click();
  await expect(page.getByRole("heading", { name: /Pronto/ })).toBeVisible();
  const antes = await perfilNoBanco(page);

  await page.getByRole("link", { name: "refazer preferências" }).click();
  await expect(radio(page, "25–34")).toBeChecked();
  await clicar(radio(page, "Prefiro não dizer"));
  await page.getByRole("button", { name: "Avançar" }).click();
  await page.getByRole("button", { name: "Avançar" }).click();
  await expect(caixa(page, "Kabum")).toBeChecked();
  await clicar(caixa(page, "Não tenho preferência"));
  await page.getByRole("button", { name: "Concluir" }).click();

  await expect(page.getByRole("heading", { name: /Pronto/ })).toBeVisible();
  const depois = await perfilNoBanco(page);
  expect(depois.id).toBe(antes.id);
  expect(depois).toMatchObject({ genero: "prefiro-nao-dizer", lojas: [] });
});

test("falha ao salvar mostra o erro, mantém as escolhas e deixa tentar de novo", async ({ page }) => {
  await passo1(page);
  await page.getByRole("button", { name: "Avançar" }).click();
  await clicar(caixa(page, "Ludopedia"));

  await page.route("**/api/v1/perfis", (r) => r.fulfill({ status: 500, body: "{}" }));
  await page.getByRole("button", { name: "Concluir" }).click();
  await expect(page.getByRole("alert")).toContainText("Não deu para salvar");
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(caixa(page, "Ludopedia")).toBeChecked();

  await page.unroute("**/api/v1/perfis");
  await page.getByRole("button", { name: "Tentar de novo" }).click();
  await expect(page.getByRole("heading", { name: /Pronto/ })).toBeVisible();
  expect((await perfilNoBanco(page)).lojas).toEqual(["ludopedia"]);
});

test("erro ao carregar as opções deixa o Avançar desabilitado", async ({ page }) => {
  await page.route("**/api/v1/lojas", (r) => r.fulfill({ status: 503, body: "{}" }));
  await page.goto("/onboarding");
  await clicar(radio(page, "18–24"));
  await page.getByRole("button", { name: "Avançar" }).click();
  await expect(page.getByRole("alert")).toContainText("Não deu para carregar");
  await expect(page.getByRole("button", { name: "Avançar" })).toBeDisabled();
});

test("regressão: no celular a grade de categorias estourava a largura da tela", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/onboarding");
  await clicar(radio(page, "25–34"));
  await page.getByRole("button", { name: "Avançar" }).click();
  await expect(caixa(page, "Games")).toBeAttached();
  const largura = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(largura).toBeLessThanOrEqual(390);
});

test("dá para fazer tudo pelo teclado", async ({ page }) => {
  await page.goto("/onboarding");
  await expect(page.getByRole("heading", { name: "Sobre você" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(radio(page, "até 17")).toBeFocused();
  await page.keyboard.press("ArrowRight"); // setas escolhem dentro do grupo
  await expect(radio(page, "18–24")).toBeChecked();
  const avancar = page.getByRole("button", { name: "Avançar" });
  await avancar.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "O que você procura?" })).toBeFocused();
  await page.keyboard.press("Tab"); // passo feito no índice ("Sobre você"): volta se apertar
  await expect(page.getByRole("button", { name: "Sobre você" })).toBeFocused();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Space");
  await expect(page.getByRole("checkbox").first()).toBeChecked();
});

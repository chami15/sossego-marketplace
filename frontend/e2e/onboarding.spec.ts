import { expect, test, type Page } from "@playwright/test";

const chip = (p: Page, nome: string) => p.getByRole("button", { name: nome, exact: true });

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
  await chip(page, "25–34").click();
  await expect(chip(page, "25–34")).toHaveAttribute("aria-pressed", "true");
  await avancar.click();
}

test("onboarding completo grava o perfil anônimo com os limites de 3", async ({ page }) => {
  await passo1(page);

  await expect(page.getByRole("heading", { name: "O que você procura?" })).toBeVisible();
  for (const c of ["Games", "Jogos de tabuleiro", "Informática"]) await chip(page, c).click();
  await chip(page, "Livros").click();
  await expect(page.getByRole("status")).toContainText("Máximo 3");
  await expect(chip(page, "Livros")).toHaveAttribute("aria-pressed", "false");
  await expect(chip(page, "Games")).toHaveAttribute("aria-pressed", "true"); // a mais antiga não sai sozinha

  const termos = page.getByLabel("Tem algo específico em mente?");
  await termos.fill("PS5");
  await termos.press("Enter");
  await termos.fill("Dixit,air fryer,");
  await expect(page.getByRole("list", { name: "Termos adicionados" }).getByRole("listitem")).toHaveCount(3);
  await page.getByRole("button", { name: "Remover air fryer" }).click();
  await page.getByRole("button", { name: "Avançar" }).click();

  await expect(page.getByRole("heading", { name: "Lojas de confiança" })).toBeVisible();
  await expect(chip(page, "Não tenho preferência")).toHaveAttribute("aria-pressed", "true");
  for (const l of ["Kabum", "Ludopedia", "Ri Happy"]) await chip(page, l).click();
  await expect(chip(page, "Não tenho preferência")).toHaveAttribute("aria-pressed", "false");
  await chip(page, "Amazon").click();
  await expect(page.getByRole("status")).toContainText("Máximo 3");
  await page.getByRole("button", { name: "Concluir" }).click();

  await expect(page.getByRole("heading", { name: "Pronto. Suas preferências estão salvas." })).toBeVisible();
  const p = await perfilNoBanco(page);
  expect(p).toMatchObject({ faixa_etaria: "25-34", genero: null, interesses: ["ps5", "dixit"] });
  // O banco devolve categorias e lojas na ordem dele; o que importa é o conjunto.
  expect([...p.categorias].sort()).toEqual(["games", "informatica", "jogos-tabuleiro"]);
  expect([...p.lojas].sort()).toEqual(["kabum", "ludopedia", "ri-happy"]);
});

test("refazer preferências volta com as escolhas e salva no mesmo perfil", async ({ page }) => {
  await passo1(page);
  await page.getByRole("button", { name: "Avançar" }).click();
  await chip(page, "Kabum").click();
  await page.getByRole("button", { name: "Concluir" }).click();
  await expect(page.getByRole("heading", { name: /Pronto/ })).toBeVisible();
  const antes = await perfilNoBanco(page);

  await page.getByRole("link", { name: "refazer preferências" }).click();
  await expect(chip(page, "25–34")).toHaveAttribute("aria-pressed", "true");
  await chip(page, "Prefiro não dizer").click();
  await page.getByRole("button", { name: "Avançar" }).click();
  await page.getByRole("button", { name: "Avançar" }).click();
  await expect(chip(page, "Kabum")).toHaveAttribute("aria-pressed", "true");
  await chip(page, "Não tenho preferência").click();
  await page.getByRole("button", { name: "Concluir" }).click();

  await expect(page.getByRole("heading", { name: /Pronto/ })).toBeVisible();
  const depois = await perfilNoBanco(page);
  expect(depois.id).toBe(antes.id);
  expect(depois).toMatchObject({ genero: "prefiro-nao-dizer", lojas: [] });
});

test("falha ao salvar mostra o erro, mantém as escolhas e deixa tentar de novo", async ({ page }) => {
  await passo1(page);
  await page.getByRole("button", { name: "Avançar" }).click();
  await chip(page, "Ludopedia").click();

  await page.route("**/api/v1/perfis", (r) => r.fulfill({ status: 500, body: "{}" }));
  await page.getByRole("button", { name: "Concluir" }).click();
  await expect(page.getByRole("alert")).toContainText("Não conseguimos salvar");
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(chip(page, "Ludopedia")).toHaveAttribute("aria-pressed", "true");

  await page.unroute("**/api/v1/perfis");
  await page.getByRole("button", { name: "Tentar de novo" }).click();
  await expect(page.getByRole("heading", { name: /Pronto/ })).toBeVisible();
  expect((await perfilNoBanco(page)).lojas).toEqual(["ludopedia"]);
});

test("dá para fazer tudo pelo teclado", async ({ page }) => {
  await page.goto("/onboarding");
  await page.keyboard.press("Tab");
  await expect(chip(page, "até 17")).toBeFocused();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Space");
  await expect(chip(page, "18–24")).toHaveAttribute("aria-pressed", "true");
  const avancar = page.getByRole("button", { name: "Avançar" });
  await avancar.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "O que você procura?" })).toBeFocused();
});

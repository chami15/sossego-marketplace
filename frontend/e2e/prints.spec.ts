import { expect, test, type Page } from "@playwright/test";

// Prints para o dono aprovar o visual (desktop 1440 e celular 390), com a API
// de verdade no banco de e2e. Saem em docs/prints/fase-06/.
// Desktop: a tela como ela é (painel fixo). Celular: página inteira, com a barra
// de ações posta no fluxo só durante a captura (fixa, ela cobriria o conteúdo).
const TELAS = [
  { nome: "desktop", viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, inteira: false },
  { nome: "mobile", viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, inteira: true },
];

const radio = (p: Page, nome: string) => p.getByRole("radio", { name: nome, exact: true });
const caixa = (p: Page, nome: string) => p.getByRole("checkbox", { name: nome, exact: true });
const clicar = (alvo: ReturnType<typeof radio>) => alvo.locator("xpath=..").click();

for (const tela of TELAS) {
  test.describe(tela.nome, () => {
    // Sem transição: o print não pega cor no meio da animação.
    test.use({ viewport: tela.viewport, deviceScaleFactor: tela.deviceScaleFactor, reducedMotion: "reduce" });

    const foto = async (page: Page, n: string) => {
      await page.mouse.move(0, 0); // sem hover acidental no print
      const estilo = tela.inteira ? await page.addStyleTag({ content: ".acoes{position:static}" }) : null;
      await page.screenshot({ path: `../docs/prints/fase-06/${tela.nome}-${n}.png`, fullPage: tela.inteira });
      await estilo?.evaluate((e) => (e as Element).remove());
    };

    test("fluxo", async ({ page }) => {
      await page.goto("/onboarding");
      await expect(page.getByRole("heading", { name: "Sobre você" })).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      await foto(page, "01-passo1-vazio");

      await clicar(radio(page, "25–34"));
      await clicar(radio(page, "Prefiro não dizer"));
      await foto(page, "02-passo1-selecionado");
      await page.getByRole("button", { name: "Avançar" }).click();

      await expect(page.getByRole("heading", { name: "O que você procura?" })).toBeVisible();
      for (const c of ["Games", "Jogos de tabuleiro", "Informática"]) await clicar(caixa(page, c));
      await page.getByLabel("Algo específico?").fill("PS5,Dixit,");
      await page.locator("body").click({ position: { x: 1, y: 1 } });
      await foto(page, "03-passo2-selecionado");
      await clicar(caixa(page, "Livros"));
      await expect(page.getByRole("status")).toContainText("Máximo 3");
      await foto(page, "04-passo2-limite-de-3");
      await page.getByRole("button", { name: "Avançar" }).click();

      await expect(page.getByRole("heading", { name: "Lojas de confiança" })).toBeVisible();
      await foto(page, "05-passo3-sem-preferencia");
      await page.getByRole("searchbox", { name: "Buscar loja" }).fill("ca");
      await foto(page, "06-passo3-busca");
      await page.getByRole("searchbox", { name: "Buscar loja" }).fill("");
      for (const l of ["Kabum", "Ludopedia", "Ri Happy"]) await clicar(caixa(page, l));
      await foto(page, "07-passo3-selecionado");
      await clicar(caixa(page, "Amazon"));
      await expect(page.getByRole("status")).toContainText("Máximo 3");
      await foto(page, "08-passo3-limite-de-3");

      await page.route("**/api/v1/perfis", (r) => r.fulfill({ status: 500, body: "{}" }));
      await page.getByRole("button", { name: "Concluir" }).click();
      await expect(page.getByRole("alert")).toBeVisible();
      await foto(page, "09-erro-ao-salvar");

      await page.unroute("**/api/v1/perfis");
      await page.getByRole("button", { name: "Tentar de novo" }).click();
      await expect(page.getByRole("heading", { name: /Pronto/ })).toBeVisible();
      await expect(page.getByText("Kabum, Ludopedia, Ri Happy")).toBeVisible();
      await foto(page, "11-pronto");
    });

    test("erro ao carregar opções", async ({ page }) => {
      await page.route("**/api/v1/lojas", (r) => r.fulfill({ status: 503, body: "{}" }));
      await page.goto("/onboarding");
      await clicar(radio(page, "18–24"));
      await page.getByRole("button", { name: "Avançar" }).click();
      await expect(page.getByRole("alert")).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      await foto(page, "10-erro-ao-carregar");
    });
  });
}

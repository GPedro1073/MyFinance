const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const { after, before, test } = require("node:test");
const { chromium } = require(process.env.MYFINANCE_PLAYWRIGHT_MODULE || "playwright");

const origin = "http://myfinance.test";
const frontend = path.resolve(__dirname, "../frontend");
const output = process.env.MYFINANCE_SCREENSHOT_DIR;
const password = "fictional-password";
const accounts = {
    "ana@example.com": { id: 1, nome: "Ana Exemplo", email: "ana@example.com" },
    "bia@example.com": { id: 2, nome: "<img src=x> Bia Exemplo", email: "bia@example.com" }
};
const charts = `window.chartState = { active: 0, disposed: 0 };
window.Chart = class {
    constructor() { chartState.active++; }
    destroy() { chartState.active--; chartState.disposed++; }
};`;
const types = {
    ".js": "text/javascript", ".mjs": "text/javascript",
    ".css": "text/css", ".html": "text/html"
};
const tokens = new Map();

function tokenFor(user, lifespan = 3600) {
    const encode = (value) => Buffer.from(JSON.stringify(value)).toString("base64url");
    const token = [
        encode({ alg: "HS256" }),
        encode({ sub: user.id, exp: Math.floor(Date.now() / 1000) + lifespan }),
        "mock-signature"
    ].join(".");
    tokens.set(token, user);
    return token;
}

function today() {
    const now = new Date();
    return [now.getFullYear(), now.getMonth() + 1, now.getDate()]
        .map((part) => String(part).padStart(2, "0")).join("-");
}

let browser;

before(async () => {
    browser = await chromium.launch({ channel: "chrome", headless: true });
});

after(async () => {
    await browser?.close();
});

async function setup(t, viewport = { width: 1440, height: 1000 }) {
    const context = await browser.newContext({ viewport });
    t.after(() => context.close());
    const page = await context.newPage();
    const seen = [];
    const errors = [];
    const state = { failLogin: null, ttl: 3600 };
    page.on("pageerror", (error) => errors.push(error.message));

    // Exercise the session fence even when an HTTP implementation ignores abort.
    await page.addInitScript(() => {
        const original = window.fetch.bind(window);
        window.fetch = (url, options) => {
            if (window.ignoreNextMovementAbort && url === "/transacoes" && !options.method) {
                window.ignoreNextMovementAbort = false;
                return original(url, { ...options, signal: undefined });
            }
            return original(url, options);
        };
    });

    await page.route("**/*", async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        const endpoint = url.pathname;
        const method = request.method();
        const respond = (status, json) => route.fulfill({ status, json });

        if (url.origin === "https://cdn.jsdelivr.net") {
            return route.fulfill({ contentType: "text/javascript", body: charts });
        }
        if (url.origin !== origin) return route.abort();
        if (endpoint === "/app" || endpoint.startsWith("/static/")) {
            const filename = endpoint === "/app" ? "index.html" : path.basename(endpoint);
            return route.fulfill({
                contentType: types[path.extname(filename)],
                body: await fs.readFile(path.join(frontend, filename))
            });
        }

        const authHeader = request.headers().authorization;
        const user = tokens.get(authHeader?.slice("Bearer ".length));
        seen.push({ endpoint, method, user: user?.id, bearer: authHeader?.startsWith("Bearer ") ?? false });
        if (endpoint === "/auth/cadastro") {
            const data = request.postDataJSON();
            assert.deepEqual(Object.keys(data).sort(), ["email", "nome", "senha"]);
            return respond(accounts[data.email] ? 409 : 201, { id: 3, nome: data.nome, email: data.email });
        }
        if (endpoint === "/auth/login") {
            if (state.failLogin === "offline") return route.abort();
            if (state.failLogin === "unavailable") return respond(503, {});
            const data = request.postDataJSON();
            assert.deepEqual(Object.keys(data).sort(), ["email", "senha"]);
            if (data.senha !== password || !accounts[data.email]) return respond(401, {});
            const profile = accounts[data.email];
            return respond(200, {
                access_token: tokenFor(profile, state.ttl),
                token_type: "bearer",
                usuario: { ...profile, nome: "Nome que não veio de /auth/me" }
            });
        }

        if (!user || endpoint === state.unauthorized) return respond(401, {});
        if (endpoint === "/auth/me") {
            if (state.holdProfile) {
                state.holdProfile.started();
                await state.holdProfile.wait;
            }
            return respond(200, user);
        }
        if (endpoint === "/categorias") return respond(200, [{ id: 1, nome: "Moradia" }]);
        if (endpoint === "/relatorios/mensal") {
            return respond(200, {
                receitas: user.id * 2000, despesas: 50, saldo: user.id * 2000 - 50,
                despesas_por_categoria: [{ categoria: "Moradia", total: 50 }]
            });
        }
        if (endpoint === "/transacoes" && method === "GET") {
            if (state.holdMovement) {
                const hold = state.holdMovement;
                state.holdMovement = null;
                hold.started();
                const status = await hold.wait;
                return respond(status, [{ descricao: "Resposta antiga", data_transacao: today() }]);
            }
            return respond(200, [{
                id: user.id, descricao: `Movimentação ${user.id}`, tipo: "despesa",
                valor: "25.00", categoria_id: 1, data_transacao: today()
            }]);
        }
        if (endpoint === "/transacoes") return respond(state.movementError || 201, {});
        if (endpoint === "/contas-fixas") {
            return respond(200, [{
                id: user.id, descricao: `Conta fixa ${user.id}`, valor: "35.00",
                categoria_id: 1, dia_vencimento: 20, ativa: true
            }]);
        }
        if (endpoint === "/pagamentos/vencimentos") {
            return respond(200, [{
                id: user.id, descricao: `Vencimento ${user.id}`, valor: "35.00",
                status: state.paid ? "pago" : "pendente", data_vencimento: today()
            }]);
        }
        if (endpoint.endsWith("/pagar") || endpoint.endsWith("/estornar")) {
            state.paid = endpoint.endsWith("/pagar");
            return respond(200, {});
        }
        return respond(404, {});
    });

    page.on("dialog", (dialog) => dialog.accept());
    await page.goto(origin + "/app");
    return { page, context, seen, errors, state };
}

async function signIn(page, email = "ana@example.com", secret = password) {
    const form = page.locator("#form-login");
    await form.getByLabel("E-mail").fill(email);
    await form.getByLabel("Senha").fill(secret);
    await form.getByRole("button", { name: "Entrar" }).click();
}

async function dashboard(page, id = 1) {
    await page.getByRole("heading", { name: "Meu dashboard" }).waitFor();
    await page.getByRole("button", { name: /Movimentações/ }).click();
    await page.getByText(`Movimentação ${id}`, { exact: true }).waitFor();
    await page.getByRole("button", { name: /Início/ }).click();
}

async function screenshot(page, filename) {
    if (output) await page.screenshot({ path: path.join(output, filename) });
}

test("registration, profile validation, Bearer, logout and reload", async (t) => {
    const { page, seen, context, errors, state } = await setup(t);
    await page.getByRole("heading", { name: "Entrar" }).waitFor();
    assert.equal(await page.locator("#financeiro").innerText(), "");
    assert.equal(seen.length, 0);
    await screenshot(page, "myfinance-login.png");

    await page.getByRole("button", { name: "Criar conta" }).click();
    await page.getByRole("heading", { name: "Criar conta" }).waitFor();
    await screenshot(page, "myfinance-cadastro.png");
    const form = page.locator("#form-cadastro");
    await form.getByLabel("Nome").fill("Pessoa Exemplo");
    await form.getByLabel("E-mail").fill("ana@example.com");
    await form.getByLabel("Senha", { exact: true }).fill(password);
    await form.getByRole("button", { name: "Cadastrar" }).click();
    await page.getByText("Já existe uma conta com este e-mail.").waitFor();
    await form.getByLabel("E-mail").fill("novo@example.com");
    await form.getByLabel("Senha", { exact: true }).fill(password);
    await form.getByRole("button", { name: "Cadastrar" }).click();
    await page.getByText("Conta criada. Entre com seu e-mail e senha.").waitFor();

    const checking = Promise.withResolvers();
    const profile = Promise.withResolvers();
    t.after(() => profile.resolve());
    state.holdProfile = { started: checking.resolve, wait: profile.promise };
    await signIn(page);
    await checking.promise;
    assert.equal(await page.locator("#financeiro").innerText(), "");
    assert.equal(seen.filter((call) => call.bearer).length, 1);
    profile.resolve();
    state.holdProfile = null;
    await dashboard(page);
    await page.getByText("Ana Exemplo", { exact: true }).waitFor();
    await screenshot(page, "myfinance-dashboard.png");
    const protectedCalls = seen.filter(({ endpoint }) => !["/auth/login", "/auth/cadastro"].includes(endpoint));
    assert.equal(protectedCalls[0].endpoint, "/auth/me");
    assert.ok(protectedCalls.every((call) => call.user === 1 && call.bearer));
    assert.ok(seen.filter(({ endpoint }) => ["/auth/login", "/auth/cadastro"].includes(endpoint))
        .every((call) => !call.bearer));
    assert.deepEqual(await page.evaluate(() => [localStorage.length, sessionStorage.length]), [0, 0]);
    assert.deepEqual(await context.cookies(), []);
    assert.equal(page.url(), origin + "/app");

    await page.getByRole("button", { name: "Sair" }).click();
    assert.equal(await page.locator("#financeiro").innerText(), "");
    assert.equal(await page.locator("#nome-usuario").innerText(), "");
    await signIn(page);
    await dashboard(page);
    await page.reload();
    await page.getByRole("heading", { name: "Entrar" }).waitFor();
    assert.equal(await page.locator("#financeiro").innerText(), "");
    assert.deepEqual(errors, []);
});

for (const lateStatus of [200, 401]) {
    test(`logout clears charts and forms and ignores a late HTTP ${lateStatus} across users`, async (t) => {
        const { page, state, errors } = await setup(t);
        await signIn(page);
        await dashboard(page);
        await page.getByRole("button", { name: /Gráficos/ }).click();
        await page.waitForFunction(() => window.chartState.active === 3);
        await page.getByRole("button", { name: /Movimentações/ }).click();
        await page.locator("#form-transacao").getByLabel("Descrição").fill("Rascunho privado da primeira sessão");
        await page.getByRole("button", { name: /Início/ }).click();

        const started = Promise.withResolvers();
        const delayed = Promise.withResolvers();
        state.holdMovement = { started: started.resolve, wait: delayed.promise };
        t.after(() => delayed.resolve(200));
        await page.evaluate(() => { window.ignoreNextMovementAbort = true; });
        await page.locator("#atualizar").click();
        await started.promise;
        await page.getByRole("button", { name: "Sair" }).click();
        assert.deepEqual(await page.evaluate(() => window.chartState), { active: 0, disposed: 3 });
        assert.equal(await page.locator("#financeiro canvas, #financeiro form").count(), 0);

        await signIn(page, "bia@example.com");
        await dashboard(page, 2);
        const response = page.waitForResponse((res) => res.url() === origin + "/transacoes");
        delayed.resolve(lateStatus);
        await (await response).finished();
        await page.getByRole("button", { name: /Movimentações/ }).click();
        assert.equal(await page.getByText("Resposta antiga").count(), 0);
        assert.equal(await page.getByText("Movimentação 1").count(), 0);
        assert.equal(await page.locator("#form-transacao").getByLabel("Descrição").inputValue(), "");
        assert.equal(await page.locator("#nome-usuario").textContent(), accounts["bia@example.com"].nome);
        assert.equal(await page.locator("#nome-usuario img").count(), 0);
        assert.deepEqual(errors, []);
    });
}

test("invalid login, connection errors and service unavailability stay on login", async (t) => {
    const { page, state, seen } = await setup(t);
    await signIn(page, undefined, "wrong-password");
    await page.getByText("E-mail ou senha inválidos.").waitFor();
    state.failLogin = "offline";
    await signIn(page);
    await page.getByText(/Falha de conexão/).waitFor();
    state.failLogin = "unavailable";
    await signIn(page);
    await page.getByText(/A API está indisponível/).waitFor();
    assert.ok(seen.every((call) => call.endpoint === "/auth/login"));
});

test("401 from a protected request ends the session; expiry also works without requests", async (t) => {
    const { page, state, errors } = await setup(t);
    await signIn(page);
    await dashboard(page);
    state.unauthorized = "/transacoes";
    await page.locator("#atualizar").click();
    await page.getByText("Sua sessão expirou. Entre novamente.").waitFor();
    assert.equal(await page.locator("#financeiro").innerText(), "");

    state.unauthorized = null;
    state.ttl = 4;
    await signIn(page);
    await dashboard(page);
    await page.getByText("Sua sessão expirou. Entre novamente.").waitFor({ timeout: 6000 });
    assert.equal(await page.locator("#financeiro").innerText(), "");
    assert.deepEqual(errors, []);
});

test("mobile layout and financial operations survive authentication and 404/422", async (t) => {
    const { page, state, seen, errors } = await setup(t, { width: 390, height: 844 });
    await page.getByRole("heading", { name: "Entrar" }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), 390);
    await page.getByRole("button", { name: "Criar conta" }).click();
    await page.getByRole("heading", { name: "Criar conta" }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), 390);
    await page.getByRole("button", { name: "Voltar ao login" }).click();
    await signIn(page);
    await dashboard(page);

    await page.getByRole("button", { name: /Movimentações/ }).click();
    const form = page.locator("#form-transacao");
    await form.getByLabel("Descrição").fill("Nova movimentação");
    await form.getByLabel(/Valor/).fill("12.50");
    for (const status of [404, 422, 201]) {
        state.movementError = status;
        await form.getByRole("button", { name: "Salvar movimentação" }).click();
        await page.getByText(status === 201 ? /cadastrada com sucesso/ : /Erro ao salvar/).waitFor();
        assert.ok(await page.getByRole("button", { name: "Sair" }).isVisible());
    }
    await page.getByRole("button", { name: /Contas fixas/ }).click();
    await page.getByText("Conta fixa 1", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Marcar como pago" }).click();
    await page.getByRole("button", { name: "Estornar" }).waitFor();
    await page.getByRole("button", { name: "Estornar" }).click();
    await page.getByRole("button", { name: "Marcar como pago" }).waitFor();
    assert.ok(seen.some(({ endpoint, method }) => endpoint === "/transacoes" && method === "POST"));
    assert.ok(seen.some(({ endpoint }) => endpoint.endsWith("/pagar")));
    assert.ok(seen.some(({ endpoint }) => endpoint.endsWith("/estornar")));
    assert.deepEqual(errors, []);
});

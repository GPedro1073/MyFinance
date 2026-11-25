class ErroHTTP extends Error {
    constructor(status, detalhe) {
        super(detalhe);
        this.status = status;
    }
}

export async function requisitarJSON(url, opcoes = {}) {
    let resposta;
    try {
        resposta = await fetch(url, { ...opcoes, cache: "no-store" });
    } catch (erro) {
        if (opcoes.signal?.aborted) throw erro;
        throw new Error("Falha de conexão. Verifique sua rede e tente novamente.");
    }

    if (resposta.status >= 500) {
        throw new ErroHTTP(resposta.status, "A API está indisponível. Tente novamente mais tarde.");
    }
    if (resposta.status === 204) return null;

    let dados;
    try {
        dados = await resposta.json();
    } catch (erro) {
        if (opcoes.signal?.aborted) throw erro;
        if (resposta.ok) throw new Error("A API retornou uma resposta inválida.");
    }

    if (!resposta.ok) {
        const detalhe = typeof dados?.detail === "string"
            ? dados.detail
            : resposta.status === 422
                ? "Revise os dados informados e tente novamente."
                : `Erro HTTP ${resposta.status}`;
        throw new ErroHTTP(resposta.status, detalhe);
    }
    return dados;
}

function expiraEm(token) {
    try {
        const payload = token.split(".")[1].replaceAll("-", "+").replaceAll("_", "/");
        const { exp } = JSON.parse(atob(payload));
        if (Number.isFinite(exp)) return exp * 1000;
    } catch {
        // /auth/me continua sendo a validação autoritativa.
    }
    return NaN;
}

export function criarSessao(token, aoEncerrar) {
    const controller = new AbortController();
    const expiracao = expiraEm(token);
    let timer;

    function encerrar(mensagem = "") {
        if (controller.signal.aborted) return;
        token = null;
        clearTimeout(timer);
        controller.abort();
        aoEncerrar(mensagem);
    }

    function expirar() {
        encerrar("Sua sessão expirou. Entre novamente.");
    }

    function verificar() {
        if (Date.now() >= expiracao && !controller.signal.aborted) expirar();
        controller.signal.throwIfAborted();
    }

    function agendarExpiracao() {
        const restante = expiracao - Date.now();
        if (restante <= 0) {
            expirar();
            return;
        }
        timer = setTimeout(agendarExpiracao, Math.min(restante, 2_147_483_647));
    }

    async function requisicao(url, opcoes = {}) {
        verificar();
        const headers = new Headers(opcoes.headers);
        headers.set("Authorization", `Bearer ${token}`);

        try {
            const dados = await requisitarJSON(url, {
                ...opcoes,
                headers,
                signal: controller.signal
            });
            verificar();
            return dados;
        } catch (erro) {
            if (erro.status === 401 && !controller.signal.aborted) expirar();
            verificar();
            throw erro;
        }
    }

    if (Number.isFinite(expiracao)) timer = setTimeout(agendarExpiracao, 0);
    return { requisicao, verificar, encerrar, signal: controller.signal };
}

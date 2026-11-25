import { montarFinanceiro } from "./app.js";
import { criarSessao, requisitarJSON } from "./sessao.mjs";

const $ = (id) => document.getElementById(id);
const login = $("form-login");
const cadastro = $("form-cadastro");
const status = $("mensagem-acesso");
const financeiro = $("financeiro");
let sessao = null;
let desmontar = null;

function exibirFormulario(formulario, mensagem = "") {
    login.hidden = formulario !== login;
    cadastro.hidden = formulario !== cadastro;
    const entrando = formulario === login;
    $("titulo-acesso").textContent = entrando ? "Entrar" : "Criar conta";
    status.textContent = mensagem;
    formulario.elements[entrando ? "email" : "nome"].focus();
}

function limparSessao(mensagem) {
    sessao = null;
    desmontar?.();
    desmontar = null;
    financeiro.replaceChildren();
    $("nome-usuario").textContent = "";
    $("usuario-sessao").hidden = true;
    $("topo").classList.remove("autenticado");
    $("acesso").hidden = false;
    login.reset();
    cadastro.reset();
    exibirFormulario(login, mensagem);
}

function enviarFormulario(url, campos) {
    return requisitarJSON(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.fromEntries(campos))
    });
}

function configurarEnvio(formulario, enviar) {
    formulario.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        const botao = formulario.querySelector("[type=submit]");
        if (botao.disabled) return;

        status.textContent = "";
        botao.disabled = true;
        $("mostrar-cadastro").disabled = true;
        $("mostrar-login").disabled = true;
        try {
            await enviar(new FormData(formulario));
        } finally {
            formulario.elements.senha.value = "";
            botao.disabled = false;
            $("mostrar-cadastro").disabled = false;
            $("mostrar-login").disabled = false;
        }
    });
}

configurarEnvio(login, async (campos) => {
    let autenticada;
    try {
        const resposta = await enviarFormulario("/auth/login", campos);
        if (!resposta?.access_token || typeof resposta.access_token !== "string") {
            throw new Error("A API não retornou uma sessão válida.");
        }

        autenticada = criarSessao(resposta.access_token, limparSessao);
        sessao = autenticada;
        const usuario = await autenticada.requisicao("/auth/me");
        autenticada.verificar();

        const raiz = document.createElement("div");
        raiz.append($("modelo-financeiro").content.cloneNode(true));
        financeiro.append(raiz);
        $("nome-usuario").textContent = usuario.nome;
        $("topo").classList.add("autenticado");
        $("usuario-sessao").hidden = false;
        $("acesso").hidden = true;
        login.reset();
        cadastro.reset();
        desmontar = montarFinanceiro(raiz, autenticada);
        $("sair").focus();
    } catch (erro) {
        if (autenticada?.signal.aborted) return;
        if (autenticada) {
            autenticada.encerrar(erro.message);
        } else {
            status.textContent = erro.status === 401 ? "E-mail ou senha inválidos." : erro.message;
        }
    }
});

configurarEnvio(cadastro, async (campos) => {
    try {
        await enviarFormulario("/auth/cadastro", campos);
        cadastro.reset();
        login.elements.email.value = campos.get("email");
        exibirFormulario(login, "Conta criada. Entre com seu e-mail e senha.");
    } catch (erro) {
        status.textContent = erro.status === 409
            ? "Já existe uma conta com este e-mail."
            : erro.message;
    }
});

$("mostrar-cadastro").addEventListener("click", () => {
    login.elements.senha.value = "";
    exibirFormulario(cadastro);
});
$("mostrar-login").addEventListener("click", () => {
    cadastro.elements.senha.value = "";
    exibirFormulario(login);
});
$("sair").addEventListener("click", () => sessao?.encerrar());


const $ = (id) => document.getElementById(id);

const moeda = (valor) =>
    new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL"
    }).format(Number(valor));

const dataLocal = () => {
    const agora = new Date();
    const ano = agora.getFullYear();
    const mes = String(agora.getMonth() + 1).padStart(2, "0");
    const dia = String(agora.getDate()).padStart(2, "0");

    return `${ano}-${mes}-${dia}`;
};

let categorias = [];
let transacaoEmEdicao = null;

function mensagem(texto) {
    $("mensagem").textContent = texto;
}

async function requisicao(url, opcoes = {}) {
    const resposta = await fetch(url, opcoes);

    if (!resposta.ok) {
        const erro = await resposta.json().catch(() => ({}));

        const detalhe = typeof erro.detail === "string"
            ? erro.detail
            : `Erro HTTP ${resposta.status}`;

        throw new Error(detalhe);
    }

    return resposta.json();
}

function prepararFiltros() {
    const agora = new Date();

    const nomesMeses = [
        "Janeiro", "Fevereiro", "Março",
        "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro",
        "Outubro", "Novembro", "Dezembro"
    ];

    nomesMeses.forEach((nome, indice) => {
        const opcao = document.createElement("option");
        opcao.value = indice + 1;
        opcao.textContent = nome;
        $("mes").appendChild(opcao);
    });

    $("mes").value = agora.getMonth() + 1;
    $("ano").value = agora.getFullYear();
    $("data").value = dataLocal();
}

async function carregarCategorias() {
    categorias = await requisicao("/categorias");

    $("categoria").replaceChildren();

    categorias.forEach((categoria) => {
        const opcao = document.createElement("option");
        opcao.value = categoria.id;
        opcao.textContent = categoria.nome;
        $("categoria").appendChild(opcao);
    });
    // Carrega categorias no cadastro de contas fixas
const selectContas = $("conta-categoria");

selectContas.replaceChildren();

const placeholder = document.createElement("option");
placeholder.value = "";
placeholder.textContent = "Selecione uma categoria";
selectContas.appendChild(placeholder);

categorias.forEach((categoria) => {
    const opcao = document.createElement("option");

    opcao.value = categoria.id;
    opcao.textContent = categoria.nome;

    selectContas.appendChild(opcao);
});
}

function renderizarCategorias(itens) {
    const container = $("categorias-grafico");
    container.replaceChildren();

    if (itens.length === 0) {
        container.textContent = "Nenhuma despesa neste mês.";
        return;
    }

    const maior = Math.max(
        ...itens.map((item) => Number(item.total)),
        1
    );

    itens.forEach((item) => {
        const linha = document.createElement("div");
        linha.className = "categoria-item";

        const topo = document.createElement("div");
        topo.className = "categoria-topo";

        const nome = document.createElement("span");
        nome.textContent = item.categoria;

        const valor = document.createElement("strong");
        valor.textContent = moeda(item.total);

        topo.append(nome, valor);

        const barra = document.createElement("div");
        barra.className = "barra";

        const preenchimento = document.createElement("div");
        preenchimento.className = "barra-valor";
        preenchimento.style.width =
            `${Number(item.total) / maior * 100}%`;

        barra.appendChild(preenchimento);
        linha.append(topo, barra);
        container.appendChild(linha);
    });
}


function iniciarEdicao(transacao) {
    transacaoEmEdicao = transacao.id;

    $("descricao").value = transacao.descricao;
    $("valor").value = transacao.valor;
    $("tipo").value = transacao.tipo;
    $("categoria").value = transacao.categoria_id;
    $("data").value = transacao.data_transacao;

    $("salvar").textContent = "Salvar alterações";
    $("cancelar-edicao").hidden = false;

    $("form-transacao").scrollIntoView({
        behavior: "smooth",
        block: "center"
    });
}

function cancelarEdicao() {
    transacaoEmEdicao = null;

    $("form-transacao").reset();
    $("data").value = dataLocal();

    $("salvar").textContent = "Salvar movimentação";
    $("cancelar-edicao").hidden = true;
}

async function excluirTransacao(transacao) {
    const confirmado = confirm(
        `Deseja excluir "${transacao.descricao}" ` +
        `no valor de ${moeda(transacao.valor)}?`
    );

    if (!confirmado) {
        return;
    }

    try {
        await requisicao(
            `/transacoes/${transacao.id}`,
            { method: "DELETE" }
        );

        if (transacaoEmEdicao === transacao.id) {
            cancelarEdicao();
        }

        await atualizarDashboard();
        mensagem("Movimentação excluída com sucesso!");
    } catch (erro) {
        mensagem(`Erro ao excluir: ${erro.message}`);
    }
}



function renderizarTransacoes(transacoes, ano, mes) {
    const corpo = $("lista-transacoes");
    corpo.replaceChildren();

    const filtradas = transacoes.filter((transacao) => {
        const [a, m] = transacao.data_transacao
            .split("-")
            .map(Number);

        return a === ano && m === mes;
    });

    if (filtradas.length === 0) {
        const linha = corpo.insertRow();
        const celula = linha.insertCell();

        celula.colSpan = 6;
        celula.textContent = "Nenhuma movimentação neste mês.";
        return;
    }

    filtradas.forEach((transacao) => {
        const linha = corpo.insertRow();

        const categoria = categorias.find(
            (c) => c.id === transacao.categoria_id
        );

        const dados = [
            transacao.descricao,
            categoria?.nome ?? "Sem categoria",
            transacao.data_transacao
                .split("-")
                .reverse()
                .join("/"),
            transacao.tipo,
            moeda(transacao.valor)
        ];

        dados.forEach((valor) => {
            const celula = linha.insertCell();
            celula.textContent = valor;
        });

        linha.cells[4].className =
            transacao.tipo === "receita"
                ? "verde"
                : "vermelho";

        const acoes = linha.insertCell();
        acoes.className = "acoes";

const editar = document.createElement("button");
editar.textContent = "✏️";
editar.className = "btn-editar btn-icone";
editar.type = "button";
editar.title = "Editar movimentação";
editar.setAttribute("aria-label", "Editar movimentação");

editar.addEventListener("click", () => {
    iniciarEdicao(transacao);
});

const excluir = document.createElement("button");
excluir.textContent = "🗑️";
excluir.className = "btn-excluir btn-icone";
excluir.type = "button";
excluir.title = "Excluir movimentação";
excluir.setAttribute("aria-label", "Excluir movimentação");

excluir.addEventListener("click", () => {
    excluirTransacao(transacao);
});

        acoes.append(editar, excluir);
    });
}


async function atualizarDashboard() {
    const ano = Number($("ano").value);
    const mes = Number($("mes").value);

    if (!Number.isInteger(ano) ||
        ano < 2000 || ano > 2100) {
        mensagem("Informe um ano entre 2000 e 2100.");
        return;
    }

    try {
        mensagem("Carregando dados...");

        const [relatorio, transacoes] = await Promise.all([
            requisicao(
                `/relatorios/mensal?ano=${ano}&mes=${mes}`
            ),
            requisicao("/transacoes")
        ]);

        $("receitas").textContent = moeda(relatorio.receitas);
        $("despesas").textContent = moeda(relatorio.despesas);
        $("saldo").textContent = moeda(relatorio.saldo);

        renderizarCategorias(
            relatorio.despesas_por_categoria
        );

        renderizarTransacoes(transacoes, ano, mes);

        mensagem("");
    } catch (erro) {
        mensagem(`Erro ao carregar dados: ${erro.message}`);
    }
}


async function salvarTransacao(evento) {
    evento.preventDefault();

    const botao = $("salvar");
    botao.disabled = true;

    const idEmEdicao = transacaoEmEdicao;

    const dados = {
        descricao: $("descricao").value.trim(),
        valor: Number($("valor").value).toFixed(2),
        tipo: $("tipo").value,
        categoria_id: Number($("categoria").value),
        data_transacao: $("data").value,
        observacao: null
    };

    const editando = idEmEdicao !== null;

    const url = editando
        ? `/transacoes/${idEmEdicao}`
        : "/transacoes";

    const metodo = editando ? "PUT" : "POST";

    try {
        await requisicao(url, {
            method: metodo,
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(dados)
        });

        cancelarEdicao();

        const [ano, mes] = dados.data_transacao
            .split("-")
            .map(Number);

        $("ano").value = ano;
        $("mes").value = mes;

        await atualizarDashboard();

        mensagem(
            editando
                ? "Movimentação atualizada com sucesso!"
                : "Movimentação cadastrada com sucesso!"
        );

    } catch (erro) {
        mensagem(`Erro ao salvar: ${erro.message}`);
    } finally {
        botao.disabled = false;
    }
}


document.addEventListener("DOMContentLoaded", async () => {
    prepararFiltros();
    
    $("cancelar-edicao-conta").addEventListener(
    "click",
    cancelarEdicaoConta
    );
    $("atualizar").addEventListener(
        "click",
        atualizarDashboard
    );

    $("form-transacao").addEventListener(
        "submit",
        salvarTransacao
    );
    
    $("cancelar-edicao").addEventListener(
    "click",
    cancelarEdicao
    );
    $("form-conta-fixa").addEventListener(
    "submit",
    salvarContaFixa
);
    // Atualizar a lista de contas fixas
$("atualizar-contas").addEventListener(
    "click",
    carregarVencimentos
);

    try {
        
        await carregarCategorias();
await atualizarDashboard();
await carregarContasFixas();
    } catch (erro) {
        mensagem(`Erro ao iniciar: ${erro.message}`);
    }
});

/* NAVEGAÇÃO ENTRE PÁGINAS */

function abrirPagina(nome) {
    // Esconde todas as páginas, menos a escolhida
    document.querySelectorAll(".pagina").forEach((pagina) => {
        pagina.hidden = pagina.id !== `pagina-${nome}`;
    });

    // Destaca o botão da página atual
    document.querySelectorAll(".menu-item").forEach((botao) => {
        const ativo = botao.dataset.pagina === nome;

        botao.classList.toggle("ativo", ativo);

        if (ativo) {
            botao.setAttribute("aria-current", "page");
        } else {
            botao.removeAttribute("aria-current");
        }
    });
}

document.querySelectorAll(".menu-item").forEach((botao) => {
    botao.addEventListener("click", async () => {
        const pagina = botao.dataset.pagina;

        abrirPagina(pagina);

        if (pagina === "contas") {
    try {
        await carregarContasFixas();
        await carregarVencimentos();
    } catch (erro) {
        mensagem(`Erro ao carregar contas: ${erro.message}`);
    }
}
    });
});

abrirPagina("inicio");

/* =====================================
   GRÁFICOS - MYFINANCE 2.0
===================================== */

let graficos = {};

// Cores do nosso tema futurista
const coresGraficos = {
    azul: "#60a5fa",
    roxo: "#a78bfa",
    verde: "#34d399",
    rosa: "#fb7185",
    amarelo: "#fbbf24",
    texto: "#cbd5e1",
    grade: "rgba(148, 163, 184, 0.12)"
};

function criarGrafico(id, configuracao) {
    // Remove a versão anterior antes de atualizar
    if (graficos[id]) {
        graficos[id].destroy();
    }

    const canvas = document.getElementById(id);

    graficos[id] = new Chart(canvas, configuracao);
}

function opcoesComuns() {
    return {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: {
                labels: {
                    color: coresGraficos.texto
                }
            },
            tooltip: {
                callbacks: {
                    label: (contexto) => {
                        const valor = contexto.parsed;

                        if (typeof valor === "number") {
                            return `${contexto.label}: ${moeda(valor)}`;
                        }

                        return `${contexto.dataset.label}: ${moeda(valor.y)}`;
                    }
                }
            }
        }
    };
}

// GRÁFICO 1 - DESPESAS POR CATEGORIA

function desenharRosca(categorias) {
    criarGrafico("grafico-rosca", {
        type: "doughnut",
        data: {
            labels: categorias.map(c => c.categoria),
            datasets: [{
                data: categorias.map(c => Number(c.total)),
                backgroundColor: [
                    coresGraficos.azul,
                    coresGraficos.roxo,
                    coresGraficos.verde,
                    coresGraficos.rosa,
                    coresGraficos.amarelo
                ],
                borderColor: "#17243a",
                borderWidth: 3,
                hoverOffset: 10
            }]
        },
        options: {
            ...opcoesComuns(),
            cutout: "68%"
        }
    });
}

// GRÁFICO 2 - RECEITAS E DESPESAS

function desenharBarras(historico) {
    criarGrafico("grafico-barras", {
        type: "bar",
        data: {
            labels: historico.map(h => h.mes),
            datasets: [
                {
                    label: "Receitas",
                    data: historico.map(h => h.receitas),
                    backgroundColor: coresGraficos.verde,
                    borderRadius: 6
                },
                {
                    label: "Despesas",
                    data: historico.map(h => h.despesas),
                    backgroundColor: coresGraficos.azul,
                    borderRadius: 6
                }
            ]
        },
        options: {
            ...opcoesComuns(),
            scales: {
                x: {
                    ticks: { color: coresGraficos.texto },
                    grid: { display: false }
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: coresGraficos.texto,
                        callback: valor => moeda(valor)
                    },
                    grid: { color: coresGraficos.grade }
                }
            }
        }
    });
}

// GRÁFICO 3 - EVOLUÇÃO DO SALDO

function desenharLinha(historico) {
    criarGrafico("grafico-linha", {
        type: "line",
        data: {
            labels: historico.map(h => h.mes),
            datasets: [{
                label: "Saldo mensal",
                data: historico.map(h => h.saldo),
                borderColor: coresGraficos.roxo,
                backgroundColor: "rgba(167,139,250,0.12)",
                fill: true,
                tension: 0.35,
                pointRadius: 5,
                pointBackgroundColor: coresGraficos.roxo
            }]
        },
        options: {
            ...opcoesComuns(),
            scales: {
                x: {
                    ticks: { color: coresGraficos.texto },
                    grid: { display: false }
                },
                y: {
                    ticks: {
                        color: coresGraficos.texto,
                        callback: valor => moeda(valor)
                    },
                    grid: { color: coresGraficos.grade }
                }
            }
        }
    });
}

// CARREGAR DADOS REAIS DO POSTGRESQL

async function atualizarGraficos() {
    if (typeof Chart === "undefined") {
        mensagem("Erro: biblioteca Chart.js não carregada.");
        return;
    }

    const ano = Number($("ano").value);
    const mes = Number($("mes").value);

    if (!Number.isInteger(ano) ||
        ano < 2000 || ano > 2100 ||
        !Number.isInteger(mes) ||
        mes < 1 || mes > 12) {
        mensagem("Selecione um mês e ano válidos.");
        return;
    }

    try {
        mensagem("Carregando gráficos...");

        // Últimos seis meses, incluindo o selecionado
        const periodos = [];

        for (let i = 5; i >= 0; i--) {
            const data = new Date(ano, mes - 1 - i, 1);

            periodos.push({
                ano: data.getFullYear(),
                mes: data.getMonth() + 1,
                nome: data.toLocaleDateString("pt-BR", {
                    month: "short",
                    year: "2-digit"
                })
            });
        }

        // Consulta nossa API FastAPI
        const historico = await Promise.all(
            periodos.map(async (periodo) => {
                const dados = await requisicao(
                    `/relatorios/mensal?ano=${periodo.ano}&mes=${periodo.mes}`
                );

                return {
                    mes: periodo.nome,
                    receitas: Number(dados.receitas),
                    despesas: Number(dados.despesas),
                    saldo: Number(dados.saldo),
                    categorias: dados.despesas_por_categoria
                };
            })
        );

        // Último mês do histórico = mês selecionado
        const atual = historico[historico.length - 1];

        desenharRosca(atual.categorias);
        desenharBarras(historico);
        desenharLinha(historico);

        mensagem("");

    } catch (erro) {
        mensagem(`Erro nos gráficos: ${erro.message}`);
    }
}

// Atualiza os gráficos ao abrir a aba Gráficos
document.querySelectorAll(".menu-item").forEach(botao => {
    if (botao.dataset.pagina === "graficos") {
        botao.addEventListener("click", () => {
            atualizarGraficos();
        });
    }
});

// Atualiza os gráficos se mudar o período
document.getElementById("atualizar").addEventListener(
    "click",
    () => {
        if (!document.getElementById("pagina-graficos").hidden) {
            atualizarGraficos();
        }
    }
);

/* ======================================
   CADASTRO DE CONTAS FIXAS
====================================== */

async function salvarContaFixa(evento) {
    evento.preventDefault();

    const botao = $("salvar-conta");
    botao.disabled = true;

    const editando = contaFixaEmEdicao !== null;

    const dados = {
        descricao: $("conta-descricao").value.trim(),
        valor: Number($("conta-valor").value).toFixed(2),
        dia_vencimento: Number($("conta-vencimento").value),
        categoria_id: Number($("conta-categoria").value),
        ativa: true
    };

    try {
        // Mantém o status atual quando estamos editando
        if (editando) {
            const contaAtual = await requisicao(
                `/contas-fixas/${contaFixaEmEdicao}`
            );

            dados.ativa = contaAtual.ativa;
        }

        const url = editando
            ? `/contas-fixas/${contaFixaEmEdicao}`
            : "/contas-fixas";

        await requisicao(url, {
            method: editando ? "PUT" : "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(dados)
        });

        cancelarEdicaoConta();

        await carregarContasFixas();
        await carregarVencimentos();
        await atualizarDashboard();

        mensagem(
            editando
                ? "Conta fixa atualizada com sucesso!"
                : "Conta fixa cadastrada com sucesso!"
        );

    } catch (erro) {
        mensagem(`Erro ao salvar conta: ${erro.message}`);
    } finally {
        botao.disabled = false;
    }
}

async function carregarContasFixas() {
    const contas = await requisicao("/contas-fixas");
    const tabela = $("lista-cadastros-fixos");

    tabela.replaceChildren();

    if (contas.length === 0) {
        const linha = tabela.insertRow();
        const celula = linha.insertCell();

        celula.colSpan = 6;
        celula.textContent = "Nenhuma despesa fixa cadastrada.";
        return;
    }

    contas.forEach((conta) => {
        const linha = tabela.insertRow();

        const categoria = categorias.find(
            c => c.id === conta.categoria_id
        );

        const dados = [
            conta.descricao,
            categoria?.nome ?? "Sem categoria",
            moeda(conta.valor),
            `Dia ${conta.dia_vencimento}`,
            conta.ativa ? "Ativa" : "Inativa"
        ];

        dados.forEach((valor) => {
            const celula = linha.insertCell();
            celula.textContent = valor;
        });

        const acoes = linha.insertCell();
        acoes.className = "acoes";

        const editar = document.createElement("button");
        editar.type = "button";
        editar.textContent = "✏️";
        editar.className = "btn-editar btn-icone";
        editar.title = "Editar conta fixa";

        editar.addEventListener("click", () => {
            editarContaFixa(conta);
        });

        const excluir = document.createElement("button");
        excluir.type = "button";
        excluir.textContent = "🗑️";
        excluir.className = "btn-excluir btn-icone";
        excluir.title = "Excluir conta fixa";

        excluir.addEventListener("click", () => {
            excluirContaFixa(conta);
        });

        const ativar = document.createElement("button");
        ativar.type = "button";
        ativar.textContent = conta.ativa ? "Desativar" : "Ativar";
        ativar.className = "botao-secundario";

        ativar.addEventListener("click", () => {
            desativarContaFixa(conta);
        });

        acoes.append(editar, excluir, ativar);
    });
}
// =====================================
// VENCIMENTOS E PAGAMENTOS
// =====================================

async function carregarVencimentos() {
    const hoje = new Date();
    const ano = Number($("ano").value) || hoje.getFullYear();
    const mes = Number($("mes").value) || hoje.getMonth() + 1;

    const vencimentos = await requisicao(
        `/pagamentos/vencimentos?ano=${ano}&mes=${mes}`
    );

    const tabela = $("lista-contas");
    tabela.replaceChildren();

    let totalPago = 0;
    let totalPendente = 0;

    vencimentos.forEach((conta) => {
        const linha = tabela.insertRow();
        const pago = conta.status === "pago";

        if (pago) {
            totalPago += Number(conta.valor);
        } else {
            totalPendente += Number(conta.valor);
        }

        const dados = [
            conta.descricao,
            conta.data_vencimento.split("-").reverse().join("/"),
            moeda(conta.valor),
            pago ? "✅ Pago" : "⏳ Pendente"
        ];

        dados.forEach((valor) => {
            const celula = linha.insertCell();
            celula.textContent = valor;
        });

        const acoes = linha.insertCell();

        const botao = document.createElement("button");
        botao.type = "button";
        botao.textContent = pago ? "Estornar" : "Marcar como pago";
        botao.className = pago
            ? "botao-secundario"
            : "botao-pagar";

        botao.addEventListener("click", async () => {
            const confirmado = confirm(
                pago
                    ? `Deseja estornar ${conta.descricao}?`
                    : `Confirmar pagamento de ${conta.descricao}?`
            );

            if (!confirmado) return;

            botao.disabled = true;

            try {
                const url = pago
                    ? `/pagamentos/vencimentos/${conta.id}/estornar`
                    : `/pagamentos/vencimentos/${conta.id}/pagar`;

                const opcoes = {
                    method: "POST"
                };

                if (!pago) {
                    opcoes.headers = {
                        "Content-Type": "application/json"
                    };

                    opcoes.body = JSON.stringify({
                        data_pagamento: dataLocal()
                    });
                }

                await requisicao(url, opcoes);

                await carregarVencimentos();
                await atualizarDashboard();

                mensagem(
                    pago
                        ? "Pagamento estornado com sucesso!"
                        : "Pagamento registrado com sucesso!"
                );

            } catch (erro) {
                mensagem(`Erro: ${erro.message}`);
                botao.disabled = false;
            }
        });

        acoes.appendChild(botao);
    });

    $("total-pago").textContent = moeda(totalPago);
    $("total-pendente").textContent = moeda(totalPendente);
}
// ======================================
// GERENCIAMENTO DE DESPESAS FIXAS
// ======================================

let contaFixaEmEdicao = null;

function cancelarEdicaoConta() {
    contaFixaEmEdicao = null;

    $("form-conta-fixa").reset();

    $("salvar-conta").textContent = "+ Cadastrar conta fixa";
    $("cancelar-edicao-conta").hidden = true;
}

function editarContaFixa(conta) {
    contaFixaEmEdicao = conta.id;

    $("conta-descricao").value = conta.descricao;
    $("conta-valor").value = conta.valor;
    $("conta-vencimento").value = conta.dia_vencimento;
    $("conta-categoria").value = conta.categoria_id;

    $("salvar-conta").textContent = "Salvar alterações";
    $("cancelar-edicao-conta").hidden = false;

    $("form-conta-fixa").scrollIntoView({
        behavior: "smooth",
        block: "center"
    });
}

async function excluirContaFixa(conta) {
    const confirmado = confirm(
        `Deseja excluir "${conta.descricao}"?`
    );

    if (!confirmado) return;

    try {
        await requisicao(`/contas-fixas/${conta.id}`, {
            method: "DELETE"
        });

        if (contaFixaEmEdicao === conta.id) {
            cancelarEdicaoConta();
        }

        await carregarContasFixas();
        await carregarVencimentos();

        mensagem("Conta fixa excluída com sucesso!");

    } catch (erro) {
        mensagem(`Não foi possível excluir: ${erro.message}`);
    }
}

async function desativarContaFixa(conta) {
    const dados = {
        descricao: conta.descricao,
        valor: conta.valor,
        dia_vencimento: conta.dia_vencimento,
        categoria_id: conta.categoria_id,
        ativa: !conta.ativa
    };

    try {
        await requisicao(`/contas-fixas/${conta.id}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(dados)
        });

        await carregarContasFixas();

        mensagem(
            dados.ativa
                ? "Conta reativada!"
                : "Conta desativada!"
        );

    } catch (erro) {
        mensagem(`Erro: ${erro.message}`);
    }
}
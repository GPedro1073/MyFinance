from pagamentos import router as pagamentos_router
from calendar import monthrange
from datetime import date
from decimal import Decimal
from fastapi import Query
from fastapi import FastAPI, HTTPException
from psycopg import errors
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import get_connection

from schemas import (
    TransacaoCriar,
    TransacaoAtualizar,
    TransacaoResposta,
    ContaFixaCriar,
    ContaFixaAtualizar,
    ContaFixaResposta,
)

app = FastAPI(
    title="MyFinance API",
    description="API de gerenciamento financeiro pessoal",
    version="1.0.0",
)

app.include_router(pagamentos_router)
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static"
)

@app.get("/app", include_in_schema=False)
def abrir_aplicativo():
    return FileResponse(FRONTEND_DIR / "index.html")
def verificar_transacao_vinculada(conn, transacao_id):
    vinculada = conn.execute(
        """
        SELECT id
        FROM vencimentos
        WHERE transacao_id = %s
        """,
        (transacao_id,)
    ).fetchone()

    if vinculada:
        raise HTTPException(
            status_code=409,
            detail=(
                "Transação vinculada a uma conta fixa. "
                "Utilize o endpoint de estorno."
            )
        )
    


# 1. Verificar se a API está funcionando
@app.get("/")
def inicio():
    return {"mensagem": "MyFinance API funcionando!"}


# 2. Listar categorias
@app.get("/categorias")
def listar_categorias():
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, nome FROM categorias ORDER BY nome"
        ).fetchall()


# 3. Listar todas as transações
@app.get(
    "/transacoes",
    response_model=list[TransacaoResposta]
)
def listar_transacoes():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, descricao, valor, tipo,
                   data_transacao, categoria_id, observacao
            FROM transacoes
            ORDER BY data_transacao DESC, id DESC
            """
        ).fetchall()


# 4. Consultar uma transação pelo ID
@app.get(
    "/transacoes/{transacao_id}",
    response_model=TransacaoResposta
)
def buscar_transacao(transacao_id: int):
    with get_connection() as conn:
        transacao = conn.execute(
            """
            SELECT id, descricao, valor, tipo,
                   data_transacao, categoria_id, observacao
            FROM transacoes
            WHERE id = %s
            """,
            (transacao_id,)
        ).fetchone()

    if transacao is None:
        raise HTTPException(
            status_code=404,
            detail="Transação não encontrada"
        )

    return transacao


# 5. Cadastrar uma nova transação
@app.post(
    "/transacoes",
    response_model=TransacaoResposta,
    status_code=201
)
def criar_transacao(dados: TransacaoCriar):
    try:
        with get_connection() as conn:
            transacao = conn.execute(
                """
                INSERT INTO transacoes (
                    descricao, valor, tipo,
                    data_transacao, categoria_id, observacao
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, descricao, valor, tipo,
                          data_transacao, categoria_id, observacao
                """,
                (
                    dados.descricao,
                    dados.valor,
                    dados.tipo,
                    dados.data_transacao,
                    dados.categoria_id,
                    dados.observacao,
                )
            ).fetchone()

    except errors.ForeignKeyViolation:
        raise HTTPException(
            status_code=422,
            detail="Categoria não encontrada"
        )

    return transacao


# 6. Atualizar uma transação existente
@app.put(
    "/transacoes/{transacao_id}",
    response_model=TransacaoResposta
)
def atualizar_transacao(
    transacao_id: int,
    dados: TransacaoAtualizar
):
    try:
        with get_connection() as conn:
            verificar_transacao_vinculada(conn, transacao_id)
            transacao = conn.execute(
                """
                UPDATE transacoes
                SET descricao = %s,
                    valor = %s,
                    tipo = %s,
                    data_transacao = %s,
                    categoria_id = %s,
                    observacao = %s
                WHERE id = %s
                RETURNING id, descricao, valor, tipo,
                          data_transacao, categoria_id, observacao
                """,
                (
                    dados.descricao,
                    dados.valor,
                    dados.tipo,
                    dados.data_transacao,
                    dados.categoria_id,
                    dados.observacao,
                    transacao_id,
                )
            ).fetchone()

    except errors.ForeignKeyViolation:
        raise HTTPException(
            status_code=422,
            detail="Categoria não encontrada"
        )

    if transacao is None:
        raise HTTPException(
            status_code=404,
            detail="Transação não encontrada"
        )

    return transacao


# 7. Excluir uma transação

@app.delete("/transacoes/{transacao_id}")
def excluir_transacao(transacao_id: int):
    with get_connection() as conn:
        verificar_transacao_vinculada(conn, transacao_id)

        transacao = conn.execute(
            """
            DELETE FROM transacoes
            WHERE id = %s
            RETURNING id
            """,
            (transacao_id,)
        ).fetchone()

    if transacao is None:
        raise HTTPException(
            status_code=404,
            detail="Transação não encontrada"
        )

    return {
        "mensagem": "Transação excluída com sucesso"
    }




# ====================================
# CONTAS FIXAS
# ====================================

@app.get(
    "/contas-fixas",
    response_model=list[ContaFixaResposta]
)
def listar_contas_fixas():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, descricao, valor, dia_vencimento,
                   categoria_id, ativa
            FROM contas_fixas
            ORDER BY dia_vencimento, id
            """
        ).fetchall()


@app.get(
    "/contas-fixas/{conta_id}",
    response_model=ContaFixaResposta
)
def buscar_conta_fixa(conta_id: int):
    with get_connection() as conn:
        conta = conn.execute(
            """
            SELECT id, descricao, valor, dia_vencimento,
                   categoria_id, ativa
            FROM contas_fixas
            WHERE id = %s
            """,
            (conta_id,)
        ).fetchone()

    if conta is None:
        raise HTTPException(
            status_code=404,
            detail="Conta fixa não encontrada"
        )

    return conta


@app.post(
    "/contas-fixas",
    response_model=ContaFixaResposta,
    status_code=201
)
def criar_conta_fixa(dados: ContaFixaCriar):
    try:
        with get_connection() as conn:
            conta = conn.execute(
                """
                INSERT INTO contas_fixas (
                    descricao, valor, dia_vencimento,
                    categoria_id, ativa
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, descricao, valor,
                          dia_vencimento, categoria_id, ativa
                """,
                (
                    dados.descricao,
                    dados.valor,
                    dados.dia_vencimento,
                    dados.categoria_id,
                    dados.ativa,
                )
            ).fetchone()

    except errors.ForeignKeyViolation:
        raise HTTPException(
            status_code=422,
            detail="Categoria não encontrada"
        )

    return conta


@app.put(
    "/contas-fixas/{conta_id}",
    response_model=ContaFixaResposta
)
def atualizar_conta_fixa(
    conta_id: int,
    dados: ContaFixaAtualizar
):
    try:
        with get_connection() as conn:
            conta = conn.execute(
                """
                UPDATE contas_fixas
                SET descricao = %s,
                    valor = %s,
                    dia_vencimento = %s,
                    categoria_id = %s,
                    ativa = %s
                WHERE id = %s
                RETURNING id, descricao, valor,
                          dia_vencimento, categoria_id, ativa
                """,
                (
                    dados.descricao,
                    dados.valor,
                    dados.dia_vencimento,
                    dados.categoria_id,
                    dados.ativa,
                    conta_id,
                )
            ).fetchone()

    except errors.ForeignKeyViolation:
        raise HTTPException(
            status_code=422,
            detail="Categoria não encontrada"
        )

    if conta is None:
        raise HTTPException(
            status_code=404,
            detail="Conta fixa não encontrada"
        )

    return conta

@app.delete("/contas-fixas/{conta_id}")
def excluir_conta_fixa(conta_id: int):
    with get_connection() as conn:
        vinculada = conn.execute(
            """
            SELECT id FROM vencimentos
            WHERE conta_fixa_id = %s
            LIMIT 1
            """,
            (conta_id,)
        ).fetchone()

        if vinculada:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Esta conta possui vencimentos. "
                    "Desative-a utilizando PUT."
                )
            )

        conta = conn.execute(
            """
            DELETE FROM contas_fixas
            WHERE id = %s
            RETURNING id
            """,
            (conta_id,)
        ).fetchone()

    if conta is None:
        raise HTTPException(
            status_code=404,
            detail="Conta fixa não encontrada"
        )

    return {"mensagem": "Conta fixa excluída"}




# ====================================
# RELATÓRIO MENSAL
# ====================================

@app.get("/relatorios/mensal")
def relatorio_mensal(
    ano: int = Query(ge=2000, le=2100),
    mes: int = Query(ge=1, le=12),
):
    # Primeiro dia do mês solicitado
    inicio = date(ano, mes, 1)

    # Primeiro dia do mês seguinte
    if mes == 12:
        fim = date(ano + 1, 1, 1)
    else:
        fim = date(ano, mes + 1, 1)

    with get_connection() as conn:

        # Resumo das movimentações registradas
        resumo = conn.execute(
            """
            SELECT
                COALESCE(
                    SUM(valor) FILTER (
                        WHERE tipo = 'receita'
                    ), 0
                ) AS receitas,

                COALESCE(
                    SUM(valor) FILTER (
                        WHERE tipo = 'despesa'
                    ), 0
                ) AS despesas

            FROM transacoes
            WHERE data_transacao >= %s
              AND data_transacao < %s
            """,
            (inicio, fim)
        ).fetchone()

        # Despesas agrupadas por categoria
        categorias = conn.execute(
            """
            SELECT
                c.nome AS categoria,
                SUM(t.valor) AS total

            FROM transacoes t
            JOIN categorias c
                ON t.categoria_id = c.id

            WHERE t.tipo = 'despesa'
              AND t.data_transacao >= %s
              AND t.data_transacao < %s

            GROUP BY c.id, c.nome
            ORDER BY total DESC
            """,
            (inicio, fim)
        ).fetchall()

        # Contas fixas ativas
        contas = conn.execute(
            """
            SELECT
                id, descricao, valor,
                dia_vencimento

            FROM contas_fixas
            WHERE ativa = TRUE
            ORDER BY dia_vencimento, id
            """
        ).fetchall()

    receitas = resumo["receitas"]
    despesas = resumo["despesas"]
    saldo = receitas - despesas

    # Descobre quantos dias existem no mês
    ultimo_dia = monthrange(ano, mes)[1]

    contas_previstas = []

    for conta in contas:
        # Ajusta dias 29, 30 e 31 em meses menores
        dia = min(
            conta["dia_vencimento"],
            ultimo_dia
        )

        vencimento = date(ano, mes, dia)

        contas_previstas.append({
            "id": conta["id"],
            "descricao": conta["descricao"],
            "valor": str(conta["valor"]),
            "vencimento": vencimento.isoformat()
        })

    total_contas_fixas = sum(
        (conta["valor"] for conta in contas),
        Decimal("0.00")
    )

    return {
        "ano": ano,
        "mes": mes,
        "receitas": str(receitas),
        "despesas": str(despesas),
        "saldo": str(saldo),
        "despesas_por_categoria": [
            {
                "categoria": item["categoria"],
                "total": str(item["total"])
            }
            for item in categorias
        ],
        "contas_fixas_previstas": contas_previstas,
        "total_contas_fixas_previstas": str(
            total_contas_fixas
        )
    }

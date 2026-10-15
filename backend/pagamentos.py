
from calendar import monthrange
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from psycopg import errors

from database import get_connection

router = APIRouter(
    prefix="/pagamentos",
    tags=["Pagamentos e vencimentos"]
)


class PagamentoCriar(BaseModel):
    data_pagamento: date


def gerar_vencimentos(conn, ano: int, mes: int):
    competencia = date(ano, mes, 1)
    ultimo_dia = monthrange(ano, mes)[1]

    contas = conn.execute(
        """
        SELECT id, descricao, valor,
               dia_vencimento, categoria_id
        FROM contas_fixas
        WHERE ativa = TRUE
        """
    ).fetchall()

    for conta in contas:
        dia = min(conta["dia_vencimento"], ultimo_dia)
        vencimento = date(ano, mes, dia)

        conn.execute(
            """
            INSERT INTO vencimentos (
                conta_fixa_id,
                competencia,
                data_vencimento,
                descricao,
                valor,
                categoria_id
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (conta_fixa_id, competencia)
            DO NOTHING
            """,
            (
                conta["id"],
                competencia,
                vencimento,
                conta["descricao"],
                conta["valor"],
                conta["categoria_id"],
            )
        )


@router.get("/vencimentos")
def listar_vencimentos(
    ano: int = Query(ge=2000, le=2100),
    mes: int = Query(ge=1, le=12),
):
    competencia = date(ano, mes, 1)

    with get_connection() as conn:
        gerar_vencimentos(conn, ano, mes)

        registros = conn.execute(
            """
            SELECT
                v.id,
                v.conta_fixa_id,
                v.descricao,
                v.valor,
                v.data_vencimento,
                v.transacao_id,
                t.data_transacao AS data_pagamento,
                CASE
                    WHEN v.transacao_id IS NOT NULL
                        THEN 'pago'
                    ELSE 'pendente'
                END AS status

            FROM vencimentos v
            LEFT JOIN transacoes t
                ON t.id = v.transacao_id

            WHERE v.competencia = %s
            ORDER BY v.data_vencimento, v.id
            """,
            (competencia,)
        ).fetchall()

    return registros


@router.post("/vencimentos/{vencimento_id}/pagar")
def pagar_vencimento(
    vencimento_id: int,
    dados: PagamentoCriar
):
    # A transação no banco precisa ser atômica:
    # registrar despesa + vincular pagamento.
    with get_connection() as conn:

        vencimento = conn.execute(
            """
            SELECT *
            FROM vencimentos
            WHERE id = %s
            FOR UPDATE
            """,
            (vencimento_id,)
        ).fetchone()

        if vencimento is None:
            raise HTTPException(
                status_code=404,
                detail="Vencimento não encontrado"
            )

        if vencimento["transacao_id"] is not None:
            raise HTTPException(
                status_code=409,
                detail="Esta conta já está paga"
            )

        transacao = conn.execute(
            """
            INSERT INTO transacoes (
                descricao,
                valor,
                tipo,
                data_transacao,
                categoria_id,
                observacao
            )
            VALUES (%s, %s, 'despesa', %s, %s, %s)
            RETURNING id
            """,
            (
                vencimento["descricao"],
                vencimento["valor"],
                dados.data_pagamento,
                vencimento["categoria_id"],
                "Pagamento de conta fixa"
            )
        ).fetchone()

        conn.execute(
            """
            UPDATE vencimentos
            SET transacao_id = %s
            WHERE id = %s
            """,
            (transacao["id"], vencimento_id)
        )

    return {
        "mensagem": "Pagamento registrado com sucesso",
        "vencimento_id": vencimento_id,
        "transacao_id": transacao["id"],
        "status": "pago"
    }


@router.post("/vencimentos/{vencimento_id}/estornar")
def estornar_pagamento(vencimento_id: int):
    with get_connection() as conn:
        vencimento = conn.execute(
            """
            SELECT id, transacao_id
            FROM vencimentos
            WHERE id = %s
            FOR UPDATE
            """,
            (vencimento_id,)
        ).fetchone()

        if vencimento is None:
            raise HTTPException(
                status_code=404,
                detail="Vencimento não encontrado"
            )

        if vencimento["transacao_id"] is None:
            raise HTTPException(
                status_code=409,
                detail="Esta conta já está pendente"
            )

        transacao_id = vencimento["transacao_id"]

        conn.execute(
            """
            UPDATE vencimentos
            SET transacao_id = NULL
            WHERE id = %s
            """,
            (vencimento_id,)
        )

        conn.execute(
            """
            DELETE FROM transacoes
            WHERE id = %s
            """,
            (transacao_id,)
        )

    return {
        "mensagem": "Pagamento estornado",
        "status": "pendente"
    }

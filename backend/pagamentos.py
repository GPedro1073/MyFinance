
from calendar import monthrange
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from auth import UsuarioAtual

from database import get_connection

router = APIRouter(
    prefix="/pagamentos",
    tags=["Pagamentos e vencimentos"]
)


class PagamentoCriar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_pagamento: date


def gerar_vencimentos(conn, ano: int, mes: int, usuario_id: int):
    competencia = date(ano, mes, 1)
    ultimo_dia = monthrange(ano, mes)[1]

    contas = conn.execute(
        """
        SELECT id, descricao, valor,
               dia_vencimento, categoria_id
        FROM contas_fixas
        WHERE usuario_id = %s AND ativa = TRUE
        ORDER BY id
        FOR SHARE
        """,
        (usuario_id,)
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
    usuario: UsuarioAtual,
    ano: int = Query(ge=2000, le=2100),
    mes: int = Query(ge=1, le=12),
):
    competencia = date(ano, mes, 1)

    with get_connection() as conn:
        gerar_vencimentos(conn, ano, mes, usuario["id"])

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
            JOIN contas_fixas c ON c.id = v.conta_fixa_id
            LEFT JOIN transacoes t
                ON t.id = v.transacao_id AND t.usuario_id = c.usuario_id

            WHERE v.competencia = %s AND c.usuario_id = %s
              AND (v.transacao_id IS NULL OR t.id IS NOT NULL)
            ORDER BY v.data_vencimento, v.id
            """,
            (competencia, usuario["id"])
        ).fetchall()

    return registros


def bloquear_vencimento(conn, vencimento_id: int, usuario_id: int):
    vencimento = conn.execute(
        """
        SELECT v.id, v.descricao, v.valor, v.categoria_id, v.transacao_id
        FROM vencimentos v
        JOIN contas_fixas c ON c.id = v.conta_fixa_id
        WHERE v.id = %s AND c.usuario_id = %s
          AND (v.transacao_id IS NULL OR EXISTS (
              SELECT 1 FROM transacoes t
              WHERE t.id = v.transacao_id AND t.usuario_id = c.usuario_id
          ))
        FOR UPDATE OF v
        FOR SHARE OF c
        """,
        (vencimento_id, usuario_id)
    ).fetchone()
    if vencimento is None:
        raise HTTPException(status_code=404, detail="Vencimento não encontrado")
    return vencimento


@router.post("/vencimentos/{vencimento_id}/pagar")
def pagar_vencimento(
    vencimento_id: int,
    dados: PagamentoCriar,
    usuario: UsuarioAtual,
):
    # A transação no banco precisa ser atômica:
    # registrar despesa + vincular pagamento.
    with get_connection() as conn:

        vencimento = bloquear_vencimento(conn, vencimento_id, usuario["id"])

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
                observacao,
                usuario_id
            )
            VALUES (%s, %s, 'despesa', %s, %s, %s, %s)
            RETURNING id
            """,
            (
                vencimento["descricao"],
                vencimento["valor"],
                dados.data_pagamento,
                vencimento["categoria_id"],
                "Pagamento de conta fixa",
                usuario["id"],
            )
        ).fetchone()

        conn.execute(
            """
            UPDATE vencimentos v
            SET transacao_id = %s
            FROM contas_fixas c
            WHERE v.id = %s AND c.id = v.conta_fixa_id AND c.usuario_id = %s
            """,
            (transacao["id"], vencimento_id, usuario["id"])
        )

    return {
        "mensagem": "Pagamento registrado com sucesso",
        "vencimento_id": vencimento_id,
        "transacao_id": transacao["id"],
        "status": "pago"
    }


@router.post("/vencimentos/{vencimento_id}/estornar")
def estornar_pagamento(vencimento_id: int, usuario: UsuarioAtual):
    with get_connection() as conn:
        vencimento = bloquear_vencimento(conn, vencimento_id, usuario["id"])

        if vencimento["transacao_id"] is None:
            raise HTTPException(
                status_code=409,
                detail="Esta conta já está pendente"
            )

        transacao_id = vencimento["transacao_id"]

        conn.execute(
            """
            UPDATE vencimentos v
            SET transacao_id = NULL
            FROM contas_fixas c
            WHERE v.id = %s AND c.id = v.conta_fixa_id AND c.usuario_id = %s
            """,
            (vencimento_id, usuario["id"])
        )

        transacao = conn.execute(
            """
            DELETE FROM transacoes
            WHERE id = %s AND usuario_id = %s
            RETURNING id
            """,
            (transacao_id, usuario["id"])
        ).fetchone()
        if transacao is None:
            raise HTTPException(status_code=404, detail="Vencimento não encontrado")

    return {
        "mensagem": "Pagamento estornado",
        "status": "pendente"
    }

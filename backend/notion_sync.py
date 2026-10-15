
import os
import sys
from datetime import date
from decimal import Decimal

import httpx
from dotenv import load_dotenv

from database import get_connection

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID")
NOTION_VERSION = "2026-03-11"


def dinheiro(valor):
    """Formata um Decimal como moeda brasileira."""
    valor = Decimal(str(valor))
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",")
    return "R$ " + texto.replace("X", ".")


def bloco_texto(tipo, conteudo):
    """Cria um bloco compatível com a API do Notion."""
    return {
        "object": "block",
        "type": tipo,
        tipo: {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": conteudo}
                }
            ]
        }
    }


def consultar_relatorio(ano, mes):
    inicio = date(ano, mes, 1)

    if mes == 12:
        fim = date(ano + 1, 1, 1)
    else:
        fim = date(ano, mes + 1, 1)

    with get_connection() as conn:
        totais = conn.execute(
            """
            SELECT
                COALESCE(SUM(valor) FILTER (
                    WHERE tipo = 'receita'
                ), 0) AS receitas,

                COALESCE(SUM(valor) FILTER (
                    WHERE tipo = 'despesa'
                ), 0) AS despesas

            FROM transacoes
            WHERE data_transacao >= %s
              AND data_transacao < %s
            """,
            (inicio, fim)
        ).fetchone()

        categorias = conn.execute(
            """
            SELECT c.nome, SUM(t.valor) AS total
            FROM transacoes t
            JOIN categorias c
              ON c.id = t.categoria_id
            WHERE t.tipo = 'despesa'
              AND t.data_transacao >= %s
              AND t.data_transacao < %s
            GROUP BY c.id, c.nome
            ORDER BY total DESC
            """,
            (inicio, fim)
        ).fetchall()

        pagamentos = conn.execute(
            """
            SELECT
                COALESCE(SUM(valor) FILTER (
                    WHERE transacao_id IS NOT NULL
                ), 0) AS pago,

                COALESCE(SUM(valor) FILTER (
                    WHERE transacao_id IS NULL
                ), 0) AS pendente

            FROM vencimentos
            WHERE competencia = %s
            """,
            (inicio,)
        ).fetchone()

    return {
        "receitas": totais["receitas"],
        "despesas": totais["despesas"],
        "saldo": (
            totais["receitas"] - totais["despesas"]
        ),
        "categorias": categorias,
        "pago": pagamentos["pago"],
        "pendente": pagamentos["pendente"],
    }


def montar_blocos(ano, mes, dados):
    blocos = [
        bloco_texto(
            "heading_2",
            f"Relatório MyFinance — {mes:02d}/{ano}"
        ),
        bloco_texto(
            "paragraph",
            f"Receitas: {dinheiro(dados['receitas'])}"
        ),
        bloco_texto(
            "paragraph",
            f"Despesas: {dinheiro(dados['despesas'])}"
        ),
        bloco_texto(
            "paragraph",
            f"Saldo: {dinheiro(dados['saldo'])}"
        ),
        bloco_texto(
            "heading_3",
            "Despesas por categoria"
        ),
    ]

    if dados["categorias"]:
        for item in dados["categorias"]:
            blocos.append(
                bloco_texto(
                    "bulleted_list_item",
                    f"{item['nome']}: "
                    f"{dinheiro(item['total'])}"
                )
            )
    else:
        blocos.append(
            bloco_texto(
                "paragraph",
                "Nenhuma despesa registrada."
            )
        )

    blocos.extend([
        bloco_texto(
            "heading_3",
            "Contas fixas"
        ),
        bloco_texto(
            "paragraph",
            f"Pagas: {dinheiro(dados['pago'])}"
        ),
        bloco_texto(
            "paragraph",
            f"Pendentes: {dinheiro(dados['pendente'])}"
        ),
    ])

    return blocos


def enviar_notion(blocos):
    if not NOTION_TOKEN or not NOTION_PAGE_ID:
        raise ValueError(
            "Configure NOTION_TOKEN e NOTION_PAGE_ID."
        )

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    url = (
        "https://api.notion.com/v1/blocks/"
        f"{NOTION_PAGE_ID}/children"
    )

    with httpx.Client(timeout=30) as client:
        resposta = client.patch(
            url,
            headers=headers,
            json={"children": blocos}
        )

    if resposta.is_error:
        raise RuntimeError(
            f"Notion retornou HTTP {resposta.status_code}. "
            "Confira as permissões e a configuração."
        )

    return resposta.json()


def main():
    if len(sys.argv) != 3:
        print("Uso: python3 notion_sync.py ANO MES")
        return

    try:
        ano = int(sys.argv[1])
        mes = int(sys.argv[2])
        date(ano, mes, 1)

        dados = consultar_relatorio(ano, mes)
        blocos = montar_blocos(ano, mes, dados)
        enviar_notion(blocos)

        print("Relatório enviado ao Notion!")
        print(f"Competência: {mes:02d}/{ano}")
        print("Saldo:", dinheiro(dados["saldo"]))

    except (ValueError, RuntimeError, httpx.RequestError) as erro:
        print("Falha na sincronização:", erro)
        sys.exit(1)


if __name__ == "__main__":
    main()

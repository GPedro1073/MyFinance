
import os
import sys
from datetime import date

import httpx
from dotenv import load_dotenv

from notion_sync import consultar_relatorio, dinheiro

load_dotenv()

TOKEN = os.getenv("NOTION_TOKEN")
PAGE_ID = os.getenv("NOTION_PAGE_ID")

BASE_URL = "https://api.notion.com/v1"
VERSION = "2026-03-11"

MARCADOR = "[MYFINANCE_SYNC_V1]"


def texto_rico(conteudo):
    # Divide o texto para respeitar o limite
    # de 2000 caracteres por elemento do Notion.
    partes = [
        conteudo[i:i + 1500]
        for i in range(0, len(conteudo), 1500)
    ]

    return [
        {
            "type": "text",
            "text": {"content": parte}
        }
        for parte in partes
    ]


def bloco_relatorio(conteudo):
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": texto_rico(conteudo)
        }
    }


def listar_blocos(client, bloco_id):
    resultados = []
    cursor = None

    while True:
        params = {"page_size": 100}

        if cursor:
            params["start_cursor"] = cursor

        resposta = client.get(
            f"{BASE_URL}/blocks/{bloco_id}/children",
            params=params
        )
        resposta.raise_for_status()

        dados = resposta.json()
        resultados.extend(dados["results"])

        if not dados["has_more"]:
            break

        cursor = dados["next_cursor"]

    return resultados


def encontrar_pagina(client, titulo):
    blocos = listar_blocos(client, PAGE_ID)

    paginas = [
        bloco for bloco in blocos
        if bloco["type"] == "child_page"
        and bloco["child_page"]["title"] == titulo
    ]

    if len(paginas) > 1:
        raise RuntimeError(
            "Existem páginas duplicadas com esse título."
        )

    return paginas[0]["id"] if paginas else None


def criar_pagina(client, titulo):
    resposta = client.post(
        f"{BASE_URL}/pages",
        json={
            "parent": {
                "type": "page_id",
                "page_id": PAGE_ID
            },
            "properties": {
                "title": {
                    "type": "title",
                    "title": [
                        {
                            "type": "text",
                            "text": {"content": titulo}
                        }
                    ]
                }
            }
        }
    )

    resposta.raise_for_status()
    return resposta.json()["id"]


def encontrar_relatorio(client, pagina_id):
    blocos = listar_blocos(client, pagina_id)
    encontrados = []

    for bloco in blocos:
        if bloco["type"] != "paragraph":
            continue

        rich_text = bloco["paragraph"]["rich_text"]

        conteudo = "".join(
            parte.get("plain_text", "")
            for parte in rich_text
        )

        if conteudo.startswith(MARCADOR):
            encontrados.append(bloco["id"])

    if len(encontrados) > 1:
        raise RuntimeError(
            "Há mais de um bloco de sincronização."
        )

    return encontrados[0] if encontrados else None


def montar_conteudo(ano, mes, dados):
    linhas = [
        MARCADOR,
        f"Relatório financeiro — {mes:02d}/{ano}",
        "",
        f"Receitas: {dinheiro(dados['receitas'])}",
        f"Despesas: {dinheiro(dados['despesas'])}",
        f"Saldo: {dinheiro(dados['saldo'])}",
        "",
        "DESPESAS POR CATEGORIA",
    ]

    if dados["categorias"]:
        for categoria in dados["categorias"]:
            linhas.append(
                f"• {categoria['nome']}: "
                f"{dinheiro(categoria['total'])}"
            )
    else:
        linhas.append("Nenhuma despesa registrada.")

    linhas.extend([
        "",
        "CONTAS FIXAS",
        f"Pagas: {dinheiro(dados['pago'])}",
        f"Pendentes: {dinheiro(dados['pendente'])}",
    ])

    return "\n".join(linhas)


def sincronizar(ano, mes):
    if not TOKEN or not PAGE_ID:
        raise ValueError(
            "Configure NOTION_TOKEN e NOTION_PAGE_ID."
        )

    # Valida o mês solicitado.
    date(ano, mes, 1)

    dados = consultar_relatorio(ano, mes)
    conteudo = montar_conteudo(ano, mes, dados)
    titulo = f"MyFinance | {ano}-{mes:02d}"

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Notion-Version": VERSION,
        "Content-Type": "application/json",
    }

    with httpx.Client(
        headers=headers,
        timeout=30
    ) as client:

        pagina_id = encontrar_pagina(client, titulo)

        if pagina_id is None:
            pagina_id = criar_pagina(client, titulo)
            print("Página mensal criada.")
        else:
            print("Página mensal encontrada.")

        relatorio_id = encontrar_relatorio(
            client, pagina_id
        )

        bloco = bloco_relatorio(conteudo)

        if relatorio_id is None:
            resposta = client.patch(
                f"{BASE_URL}/blocks/{pagina_id}/children",
                json={"children": [bloco]}
            )
            mensagem = "Relatório criado."
        else:
            resposta = client.patch(
                f"{BASE_URL}/blocks/{relatorio_id}",
                json={"paragraph": bloco["paragraph"]}
            )
            mensagem = "Relatório atualizado."

        resposta.raise_for_status()
        print(mensagem)

    print(f"Competência: {mes:02d}/{ano}")
    print("Saldo:", dinheiro(dados["saldo"]))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(
            "Uso: python3 notion_upsert.py ANO MES"
        )

    try:
        sincronizar(
            int(sys.argv[1]),
            int(sys.argv[2])
        )
    except (
        ValueError,
        RuntimeError,
        httpx.HTTPError
    ) as erro:
        print(
            "Erro na sincronização:",
            type(erro).__name__
        )
        sys.exit(1)

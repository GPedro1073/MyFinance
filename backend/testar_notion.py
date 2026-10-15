
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("NOTION_TOKEN")
page_id = os.getenv("NOTION_PAGE_ID")

if not token or not page_id:
    raise SystemExit(
        "Configure NOTION_TOKEN e NOTION_PAGE_ID no .env"
    )

headers = {
    "Authorization": f"Bearer {token}",
    "Notion-Version": "2026-03-11",
}

url = f"https://api.notion.com/v1/pages/{page_id}"

try:
    with httpx.Client(timeout=20) as client:
        resposta = client.get(url, headers=headers)

    if resposta.status_code == 200:
        print("Conexão com o Notion funcionando!")
        print("ID da página:", resposta.json()["id"])
    else:
        print("Falha ao acessar o Notion.")
        print("Código HTTP:", resposta.status_code)
        print("Confira token, ID e permissões.")

except httpx.RequestError as erro:
    print("Erro de rede:", type(erro).__name__)

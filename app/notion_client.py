"""
Cliente real da API do Notion — Integration Token (Bearer), documentação
oficial: https://developers.notion.com/reference/intro

NÃO TESTADO contra a API real nesta sessão (mesma ressalva do mixpanel_client.py).

Usa a API atual baseada em "data source" (versão 2025-09-03 em diante) —
NÃO o endpoint antigo /v1/databases/{id}/query, que a Notion aposentou
para bases com mais de uma data source. A base "Predialize — Empresas e
Empreendimentos" já tem um data_source_id conhecido (visto ao criá-la:
a661b348-35ed-4e14-bc08-d0d84aeb10b4) — é esse valor que vai em
NOTION_DATA_SOURCE_ID, não o ID da base em si.

Diferente de como interagi com o Notion durante o projeto (via conector MCP,
autenticado com a conta pessoal da Mariana), este cliente usa uma Integration
interna do Notion — token próprio, criado em notion.so/my-integrations,
compartilhado explicitamente com a base. Isso é o que torna o acesso
institucional (não preso à conta pessoal de ninguém).
"""
import os
import httpx

NOTION_VERSION = "2025-09-03"  # checar se há versão mais nova antes de usar em produção


class NotionClient:
    def __init__(self, token: str | None = None, data_source_id: str | None = None):
        self.token = token or os.environ["NOTION_TOKEN"]
        self.data_source_id = data_source_id or os.environ["NOTION_DATA_SOURCE_ID"]
        self.base_url = "https://api.notion.com/v1"

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def empreendimentos_por_empresa(self, empresa: str) -> list[dict]:
        """
        Consulta a base de Empresas e Empreendimentos filtrando por Empresa,
        retornando os campos de cadastro (unidades, proprietários, categoria,
        automação) prontos para alimentar o gerador do painel.
        """
        payload = {
            "filter": {"property": "Empresa", "select": {"equals": empresa}},
            "page_size": 100,
        }
        resp = httpx.post(
            f"{self.base_url}/data_sources/{self.data_source_id}/query",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        rows = []
        for page in resp.json()["results"]:
            props = page["properties"]
            rows.append({
                "empreendimento": _title(props["Empreendimento"]),
                "nome_mixpanel": _rich_text(props["Nome na plataforma (Mixpanel)"]),
                "total_unidades": props["Total de unidades"]["number"],
                "proprietarios_cadastrados": props["Proprietarios cadastrados"]["number"],
                "categoria": props["Categoria"]["select"]["name"] if props["Categoria"]["select"] else None,
                "automacao_data": props["Data base automacao"]["date"]["start"] if props["Data base automacao"]["date"] else None,
                "observacoes": _rich_text(props["Observacoes"]),
            })
        return rows


def _title(prop: dict) -> str:
    return "".join(t["plain_text"] for t in prop["title"])


def _rich_text(prop: dict) -> str:
    return "".join(t["plain_text"] for t in prop["rich_text"])

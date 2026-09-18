"""
Cliente real da API do Mixpanel — Service Account (Basic Auth), usando os
MESMOS endpoints e nomes de variável de ambiente já comprovados funcionando
na ferramenta Python que já existe no VS Code da Predialize.

Histórico: a primeira versão deste arquivo usava a "Query API" mais nova
(/api/query/jql e /api/query/insights) — essas retornaram 402 Payment
Required no plano Free da Predialize. A ferramenta que já funciona usa uma
API mais antiga (/api/2.0/engage, /api/2.0/segmentation, /api/2.0/export),
que continua disponível no Free. Reescrito em cima desses três endpoints.

NÃO TESTADO CONTRA A API REAL NESTA SESSÃO — segue exatamente o padrão do
script já comprovado (mesmo API_BASE, mesmos nomes de variável, mesma auth),
mas eu não rodei isso com credencial real. Ver README.
"""
import os
import json
import httpx

API_BASE = "https://mixpanel.com/api/2.0"

CREDENTIALS = {
    "MIXPANEL": ("MIXPANEL_USERNAME", "MIXPANEL_SECRET", "MIXPANEL_PROJECT_ID"),
    "APP": ("APP_USERNAME", "APP_SECRET", "APP_PROJECT_ID"),
    "ADMIN": ("ADMIN_USERNAME", "ADMIN_SECRET", "ADMIN_PROJECT_ID"),
}


class MixpanelClient:
    def __init__(self, source: str = "APP"):
        source = source.upper()
        if source not in CREDENTIALS:
            raise ValueError(f"Fonte inválida: {source}. Use MIXPANEL, APP ou ADMIN.")
        username_var, secret_var, project_var = CREDENTIALS[source]
        self.username = os.environ[username_var]
        self.secret = os.environ[secret_var]
        self.project_id = os.environ[project_var]

    def _auth(self):
        return (self.username, self.secret)

    def fetch_people(self, limit: int = 1000) -> list[dict]:
        """Todos os perfis do projeto, paginado. Requer session_id nas páginas após a primeira."""
        results = []
        page = 0
        session_id = None
        while True:
            params = {"project_id": self.project_id, "limit": limit, "page": page}
            if session_id:
                params["session_id"] = session_id
            resp = httpx.get(f"{API_BASE}/engage", auth=self._auth(), params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            session_id = data.get("session_id", session_id)
            page_results = data.get("results", [])
            if not page_results:
                break
            results.extend(page_results)
            if len(page_results) < limit:
                break
            page += 1
        return results

    def fetch_event_export(self, event_name: str, from_date: str, to_date: str) -> list[dict]:
        """
        Eventos brutos no período. Domínio diferente de propósito — export
        de evento bruto vive em data.mixpanel.com, não em mixpanel.com onde
        ficam /engage e as outras rotas do Query API. Confirmado por
        tentativa real: mixpanel.com/api/2.0/export -> "Invalid API endpoint".
        """
        params = {
            "project_id": self.project_id,
            "event": json.dumps([event_name]),
            "from_date": from_date,
            "to_date": to_date,
            "format": "json",
        }
        resp = httpx.get("https://data.mixpanel.com/api/2.0/export", auth=self._auth(), params=params, timeout=60)
        resp.raise_for_status()
        linhas = [l for l in resp.text.splitlines() if l.strip()]
        return [json.loads(l) for l in linhas]

    def usuarios_unicos_por_empreendimento(self, empresa: str, from_date: str, to_date: str) -> dict:
        """
        Estratégia: busca os perfis (People) da empresa via /engage, monta
        distinct_id -> Enterprise; busca os eventos $session_start brutos
        via /export; junta os dois em Python, contando distinct_id únicos
        por Enterprise. Só conta usuários que aparecem nos perfis da
        empresa — evento de alguém fora da empresa é ignorado mesmo que
        apareça no export.
        """
        perfis = self.fetch_people()
        distinct_id_para_enterprise = {}
        for p in perfis:
            props = p.get("$properties", {})
            if props.get("Company") == empresa:
                did = p.get("$distinct_id")
                enterprise = props.get("Enterprise")
                if did and enterprise:
                    distinct_id_para_enterprise[did] = enterprise

        eventos = self.fetch_event_export("$session_start", from_date, to_date)

        usuarios_por_enterprise = {}
        eventos_com_match = 0
        for e in eventos:
            did = e.get("properties", {}).get("distinct_id") or e.get("distinct_id")
            enterprise = distinct_id_para_enterprise.get(did)
            if enterprise:
                eventos_com_match += 1
                usuarios_por_enterprise.setdefault(enterprise, set()).add(did)

        # Diagnóstico — imprime no log do container pra ver em qual etapa a
        # contagem está zerando, em vez de só devolver {} silenciosamente.
        print(f"[mixpanel_client] perfis totais buscados: {len(perfis)}")
        print(f"[mixpanel_client] perfis com Company == {empresa!r}: {len(distinct_id_para_enterprise)}")
        if perfis[:1]:
            print(f"[mixpanel_client] exemplo de $properties de 1 perfil: {perfis[0].get('$properties', {})}")
        print(f"[mixpanel_client] eventos $session_start totais buscados: {len(eventos)}")
        if eventos[:1]:
            print(f"[mixpanel_client] exemplo de 1 evento bruto: {eventos[0]}")
        print(f"[mixpanel_client] eventos que bateram com algum distinct_id da empresa: {eventos_com_match}")

        return {k: len(v) for k, v in usuarios_por_enterprise.items()}


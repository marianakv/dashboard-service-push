"""
Cliente real da Query API do Mixpanel — Service Account (Basic Auth),
conforme https://docs.mixpanel.com/reference/query-api-authentication.

NÃO TESTADO contra a API real nesta sessão: não há credenciais de Service
Account disponíveis no sandbox onde este código foi escrito. A implementação
segue a documentação oficial (verificada em set/2026), mas precisa de um
primeiro teste real com as credenciais da Predialize antes de confiar em
produção — ver README.md, seção "O que está provado vs. o que não está".

MÉTODO PRIMÁRIO — get_insights_report(bookmark_id): consulta um relatório
Insights já salvo no Mixpanel. É o método que a própria Mixpanel recomenda
ativamente hoje. A Predialize já tem relatórios salvos reaproveitáveis (ex.:
"Acessos no Mês (MAU)", bookmark_id 9944705, criado por Amanda Saito) —
o caminho mais seguro é: alguém com acesso ao Mixpanel salva um relatório
Insights por métrica precisada (breakdown por Enterprise, por exemplo), e
o serviço só consulta pelo bookmark_id.

MÉTODO SECUNDÁRIO, COM RESSALVA — run_jql(): a Mixpanel marca JQL como "em
manutenção" e antes tinha uma data de desligamento completo anunciada pra
31/dez/2025 — essa data foi removida da documentação depois (visto num
histórico de commit da doc oficial), o que sugere que não desligaram como
planejado, mas não há garantia. Testar isso com uma chamada real ANTES de
depender dele pra qualquer coisa importante. Mantido aqui porque replica as
consultas ad-hoc (breakdown por Enterprise, funil, frequência por usuário)
que foram feitas manualmente ao longo deste projeto e que não têm um
relatório salvo equivalente ainda.
"""
import os
import httpx


class MixpanelClient:
    def __init__(
        self,
        service_account_username: str | None = None,
        service_account_secret: str | None = None,
        project_id: str | None = None,
        region: str = "mixpanel",  # "mixpanel" (US) | "eu.mixpanel" | "in.mixpanel"
    ):
        self.username = service_account_username or os.environ["MIXPANEL_SERVICE_ACCOUNT_USERNAME"]
        self.secret = service_account_secret or os.environ["MIXPANEL_SERVICE_ACCOUNT_SECRET"]
        self.project_id = project_id or os.environ["MIXPANEL_PROJECT_ID"]
        self.base_url = f"https://{region}.com/api/query"

    def _auth(self):
        return (self.username, self.secret)

    def get_insights_report(self, bookmark_id: str, workspace_id: str | None = None) -> dict:
        """MÉTODO RECOMENDADO. Consulta um relatório Insights salvo pelo bookmark_id."""
        params = {"project_id": self.project_id, "bookmark_id": bookmark_id}
        if workspace_id:
            params["workspace_id"] = workspace_id
        resp = httpx.get(f"{self.base_url}/insights", params=params, auth=self._auth(), timeout=60)
        resp.raise_for_status()
        return resp.json()

    def run_jql(self, script: str, params: dict) -> list:
        """MÉTODO SECUNDÁRIO — ver aviso de maintenance mode no docstring do módulo."""
        import json as _json
        resp = httpx.post(
            f"{self.base_url}/jql",
            data={"script": script, "params": _json.dumps(params)},
            auth=self._auth(),
            timeout=110,  # JQL pode rodar até 2min segundo a documentação da Mixpanel
        )
        resp.raise_for_status()
        return resp.json()

    def usuarios_unicos_por_empreendimento(self, empresa: str, from_date: str, to_date: str) -> dict:
        """
        Réplica em JQL da consulta que foi rodada manualmente (via MCP) ao
        longo deste projeto: usuários únicos do evento $session_start,
        quebrado pela propriedade de perfil "Enterprise", filtrado por
        "Company" = empresa. Só usar depois de confirmar que o endpoint JQL
        ainda responde (ver aviso no topo do arquivo).

        Retorna {nome_do_empreendimento: usuarios_unicos}.
        """
        script = """
        function main() {
          return join(
            Events({
              from_date: params.from_date,
              to_date: params.to_date,
              event_selectors: [{event: "$session_start"}]
            }),
            People(),
            {type: "inner", selectors: [{selector: 'user["Company"] == "' + params.empresa + '"'}]}
          )
          .groupByUser(["user.properties.Enterprise"], mixpanel.reducer.null())
          .groupBy(["key.1"], mixpanel.reducer.count());
        }
        """
        params = {"from_date": from_date, "to_date": to_date, "empresa": empresa}
        rows = self.run_jql(script, params)
        return {row["key"][0]: row["value"] for row in rows if row["key"][0]}

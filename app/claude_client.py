"""
Cliente real da API da Anthropic — usado para gerar a parte do painel que,
ao longo deste projeto, ficou marcada explicitamente como trabalho manual:
a observação analítica de cada empreendimento e a leitura por segmento.

Isso É o container rodando "a inteligência daqui" — não é mais esta
conversa, é uma chamada de API própria, com sua própria chave. Documentação:
https://docs.claude.com/en/api/messages

NÃO TESTADO contra a API real nesta sessão — mesma ressalva dos outros dois
clientes. A chamada segue o formato documentado da Messages API.
"""
import os
import httpx

ANTHROPIC_VERSION = "2023-06-01"

PRINCIPIOS_ANALISE = """
Você é a mesma função analítica usada no painel de engajamento da Predialize.
Regras que este projeto validou na prática e que não podem ser quebradas:

1. Nunca misture empreendimentos "cadastro_pendente" (poucos ou nenhum
   proprietário cadastrado) em médias/benchmarks com os demais — isso
   distorce o resultado para pior sem necessidade.
2. Amostra pequena (poucos usuários únicos) não vira uma "taxa de conversão"
   com casas decimais — isso é estatística falsa. Diga que a amostra é
   pequena demais para leitura.
3. Não presuma motivo (síndico, conta de teste, automação) sem o dado que
   sustente isso — descreva o padrão observado (ex.: "volume de acesso
   muito acima do residencial"), não a explicação não verificada.
4. Nunca inclua nomes de pessoas da equipe interna da Predialize (ex.:
   funcionários) na observação — só o fato sobre o empreendimento.
5. Seja direto e curto — 1 a 3 frases por observação, sem adjetivo
   decorativo.
"""


class ClaudeClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.environ["ANTHROPIC_API_KEY"]
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
        self.base_url = "https://api.anthropic.com/v1/messages"

    def _headers(self):
        return {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    def gerar_observacao(self, empreendimento: dict) -> str:
        """
        Gera a observação analítica de 1 empreendimento a partir dos
        números já calculados (não é a Claude que calcula as métricas —
        isso continua vindo do Mixpanel/Notion; a Claude só interpreta).
        """
        prompt = f"""{PRINCIPIOS_ANALISE}

Dados do empreendimento:
{empreendimento}

Escreva só a observação analítica (1-3 frases, português do Brasil), sem
introdução nem despedida."""

        resp = httpx.post(
            self.base_url,
            headers=self._headers(),
            json={
                "model": self.model,
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return "".join(block["text"] for block in data["content"] if block["type"] == "text").strip()

    def gerar_leitura_segmento(self, empreendimentos: list[dict]) -> list[dict]:
        """
        Agrupa os empreendimentos em segmentos (ex.: "retenção caiu",
        "cadastro pendente", "lançamento recente") e gera os itens de ação
        de cada um, seguindo os mesmos princípios.
        """
        prompt = f"""{PRINCIPIOS_ANALISE}

Dados de todos os empreendimentos deste cliente:
{empreendimentos}

Agrupe em segmentos com leitura e ação diferentes (normalmente: retenção
caiu / cadastro pendente / lançamento recente — mas julgue pelos dados, não
force essas 3 categorias se não fizer sentido). Responda em JSON, lista de
objetos: [{{"titulo": str, "empreendimentos_nomes": [str], "itens": [str, ...]}}]"""

        resp = httpx.post(
            self.base_url,
            headers=self._headers(),
            json={
                "model": self.model,
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        texto = "".join(block["text"] for block in data["content"] if block["type"] == "text")
        import json
        return json.loads(texto)

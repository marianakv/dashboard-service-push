"""
Orquestra a geração do painel: Notion (cadastro) + Mixpanel (uso) + Claude
(observação analítica, opcional) -> template Jinja2 -> HTML final.

Este módulo é o que substitui o processo manual que rodou o projeto inteiro
até aqui (eu consultando Mixpanel e Notion via ferramentas MCP dentro da
conversa, montando o JSON à mão). A lógica de negócio — quais consultas
rodar, como classificar cada empreendimento, o que vira "cadastro_pendente"
— é a mesma; só a forma de buscar o dado mudou, de "eu numa conversa" para
"este serviço, sozinho".

ESCOPO DECLARADO: implementei a consulta de usuários únicos por
empreendimento (a métrica central). Funil, frequência de acesso,
funcionalidades mais usadas, sistema operacional e top 10 usuários seguem o
mesmo padrão de JQL/Insights, mas não foram todos escritos aqui — expandir
usando mixpanel_client.py como referência é trabalho mecânico, não uma
decisão de arquitetura nova. Ver README.
"""
import datetime
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from .mixpanel_client import MixpanelClient
from .notion_client import NotionClient
from .claude_client import ClaudeClient

CATEGORIA_NOTION_PARA_SLUG = {
    "Declinio pos-lancamento": "declinio",
    "Lancamento recente": "lancamento_recente",
    "Cadastro pendente": "cadastro_pendente",
}
CATEGORIA_LABEL = {
    "declinio": "Declínio pós-lançamento",
    "lancamento_recente": "Lançamento recente",
    "cadastro_pendente": "Cadastro pendente",
}
MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _slug(nome: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return s.lower().replace(" ", "-")


def montar_dados(
    cliente: str,
    from_date: str,
    to_date: str,
    usar_claude_para_narrativa: bool = False,
) -> dict:
    """
    Monta o dicionário de dados no formato que o template espera,
    combinando Notion (cadastro) e Mixpanel (uso). Se
    usar_claude_para_narrativa=True, chama a Claude real para escrever as
    observações — senão, deixa "observacao": None (o chamador decide o que
    fazer: preencher manualmente, ou aceitar sem narrativa).
    """
    notion = NotionClient()
    cadastro_rows = {r["empreendimento"]: r for r in notion.empreendimentos_por_empresa(cliente)}

    mixpanel = MixpanelClient()
    usuarios_por_nome_mixpanel = mixpanel.usuarios_unicos_por_empreendimento(cliente, from_date, to_date)

    claude = ClaudeClient() if usar_claude_para_narrativa else None

    empreendimentos = []
    for nome, cad in cadastro_rows.items():
        usuarios_unicos = usuarios_por_nome_mixpanel.get(cad["nome_mixpanel"], 0)
        total_unidades = cad["total_unidades"] or 0
        proprietarios = cad["proprietarios_cadastrados"] or 0
        pct_cadastrado = round(100 * proprietarios / total_unidades, 1) if total_unidades else 0.0
        taxa_unidades = round(100 * usuarios_unicos / total_unidades, 1) if total_unidades else 0.0
        taxa_cadastrados = round(100 * usuarios_unicos / proprietarios, 1) if proprietarios else None

        emp = {
            "slug": _slug(nome),
            "nome": nome,
            "nome_mixpanel": cad["nome_mixpanel"],
            "categoria": CATEGORIA_NOTION_PARA_SLUG.get(cad["categoria"], "cadastro_pendente"),
            "categoria_label": CATEGORIA_LABEL.get(CATEGORIA_NOTION_PARA_SLUG.get(cad["categoria"]), cad["categoria"]),
            "status_label": CATEGORIA_LABEL.get(CATEGORIA_NOTION_PARA_SLUG.get(cad["categoria"]), cad["categoria"]),
            "usuarios_unicos": usuarios_unicos,
            "total_unidades": total_unidades,
            "proprietarios_cadastrados": proprietarios,
            "pct_cadastrado": pct_cadastrado,
            "taxa_unidades": taxa_unidades,
            "taxa_cadastrados": taxa_cadastrados,
            "automacao_data_fmt": _formatar_data_pt(cad["automacao_data"]) if cad["automacao_data"] else None,
            "observacao": cad["observacoes"] or None,
            "anomaly_note": None,
            "benchmark_taxa": None,
            "benchmark_direcao": None,
            "cor": "#3b82f6",
            # Campos que precisam de consultas adicionais de Mixpanel (ver
            # docstring do módulo) — deixados com placeholder honesto em vez
            # de dado inventado:
            "pico": None, "mes_pico": None, "ultimo_mes_valor": None, "ultimo_mes_label": None,
            "acesso_unico_pct": None, "acesso_recorrente_pct": None,
            "at_engajamento_pct": None, "at_engajamento_n": None,
            "tendencia_mensal": [],
            "funil_viu_login": None, "funil_iniciou_sessao": None,
            "funil_conversao_pct": None, "funil_amostra_pequena": None,
        }

        if claude and not emp["observacao"]:
            emp["observacao"] = claude.gerar_observacao(emp)

        empreendimentos.append(emp)

    # Benchmark: só entre os que não são cadastro_pendente, excluindo o
    # próprio da média — mesma regra usada no projeto inteiro.
    base_real = [e for e in empreendimentos if e["categoria"] != "cadastro_pendente"]
    for e in base_real:
        outros = [o["taxa_unidades"] for o in base_real if o["slug"] != e["slug"]]
        if outros:
            e["benchmark_taxa"] = round(sum(outros) / len(outros), 1)
            e["benchmark_direcao"] = "acima" if e["taxa_unidades"] >= e["benchmark_taxa"] else "abaixo"

    dados = {
        "cliente": cliente,
        "janela_label": f"{from_date} a {to_date}",
        "janela_curta": f"{from_date} a {to_date}",
        "meses": [],  # requer a série mensal por empreendimento — ver escopo declarado
        "total_usuarios": sum(e["usuarios_unicos"] for e in empreendimentos),
        "destaque_stat": None,
        "empreendimentos": empreendimentos,
        "funcionalidades": [],
        "sistemas_construtivos": [],
        "sistema_operacional": [],
        "top10_usuarios": [],
        "segmentos": claude.gerar_leitura_segmento(empreendimentos) if claude else [],
    }
    return dados


def _formatar_data_pt(iso_date: str) -> str:
    ano, mes, dia = iso_date.split("-")
    return f"{dia}/{MESES_PT[int(mes) - 1]}/{ano[2:]}"


def renderizar(dados: dict) -> str:
    dados = dict(dados)
    emp = dados["empreendimentos"]
    dados["n_declinio"] = sum(1 for e in emp if e["categoria"] == "declinio")
    dados["n_lancamento_recente"] = sum(1 for e in emp if e["categoria"] == "lancamento_recente")
    dados["n_cadastro_pendente"] = sum(1 for e in emp if e["categoria"] == "cadastro_pendente")
    hoje = datetime.date.today()
    dados["gerado_em"] = f"{MESES_PT[hoje.month - 1].capitalize()} {hoje.year}"

    env = Environment(
        loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("dashboard_template.html.j2")
    return template.render(**dados)

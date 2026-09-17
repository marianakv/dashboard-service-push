"""
Serviço do gerador de painel de engajamento — Predialize.

    POST /paineis/{cliente}?from_date=2025-06-01&to_date=2026-07-31
        -> gera o painel ao vivo (Notion + Mixpanel [+ Claude opcional])
    GET  /saude
        -> checagem simples de que o serviço está de pé

Ver README.md para variáveis de ambiente exigidas e para o que está
provado vs. o que precisa de teste com credenciais reais.
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.generator import montar_dados, renderizar

app = FastAPI(title="Predialize — Gerador de Painel de Engajamento")


@app.get("/saude")
def saude():
    return {"status": "ok"}


@app.post("/paineis/{cliente}", response_class=HTMLResponse)
def gerar_painel(
    cliente: str,
    from_date: str = Query(..., description="AAAA-MM-DD"),
    to_date: str = Query(..., description="AAAA-MM-DD"),
    usar_claude: bool = Query(False, description="Gerar observações e leitura por segmento com a API da Claude"),
):
    try:
        dados = montar_dados(cliente, from_date, to_date, usar_claude_para_narrativa=usar_claude)
    except KeyError as e:
        raise HTTPException(status_code=500, detail=f"Variável de ambiente ausente: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Falha consultando fonte de dados: {e}")

    html = renderizar(dados)
    return HTMLResponse(content=html)

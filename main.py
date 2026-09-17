"""
Serviço do gerador de painel de engajamento — Predialize.

    GET  /
        -> redireciona para /docs
    GET  /paineis/{cliente}?from_date=2025-06-01&to_date=2026-07-31
        -> gera o painel ao vivo e devolve a página renderizada — pode ser
           aberto direto no navegador, é isso que funciona como "página
           inicial" pra ver o resultado.
    POST /paineis/{cliente}?...
        -> mesma coisa, disponível também como POST (útil se algum dia isso
           for chamado por outro serviço em vez de navegador).
    GET  /saude
        -> checagem simples de que o serviço está de pé

Ver README.md para variáveis de ambiente exigidas e para o que está
provado vs. o que precisa de teste com credenciais reais.
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.generator import montar_dados, renderizar

app = FastAPI(title="Predialize — Gerador de Painel de Engajamento")


@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse(url="/docs")


@app.get("/saude")
def saude():
    return {"status": "ok"}


def _gerar(cliente: str, from_date: str, to_date: str, usar_claude: bool) -> HTMLResponse:
    try:
        dados = montar_dados(cliente, from_date, to_date, usar_claude_para_narrativa=usar_claude)
    except KeyError as e:
        raise HTTPException(status_code=500, detail=f"Variável de ambiente ausente: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Falha consultando fonte de dados: {e}")

    html = renderizar(dados)
    return HTMLResponse(content=html)


@app.get("/paineis/{cliente}", response_class=HTMLResponse)
def gerar_painel_get(
    cliente: str,
    from_date: str = Query(..., description="AAAA-MM-DD"),
    to_date: str = Query(..., description="AAAA-MM-DD"),
    usar_claude: bool = Query(False, description="Gerar observações e leitura por segmento com a API da Claude"),
):
    """Mesma coisa que o POST abaixo, mas em GET — pra abrir direto no navegador."""
    return _gerar(cliente, from_date, to_date, usar_claude)


@app.post("/paineis/{cliente}", response_class=HTMLResponse)
def gerar_painel(
    cliente: str,
    from_date: str = Query(..., description="AAAA-MM-DD"),
    to_date: str = Query(..., description="AAAA-MM-DD"),
    usar_claude: bool = Query(False, description="Gerar observações e leitura por segmento com a API da Claude"),
):
    return _gerar(cliente, from_date, to_date, usar_claude)


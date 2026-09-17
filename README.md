# Serviço do Gerador de Painel de Engajamento — Predialize

Responde às duas coisas pedidas: (1) conexão real com o Mixpanel — não mais
eu rodando consulta manualmente dentro de uma conversa; (2) o MVP rodando
como serviço próprio, containerizado, usando a API da Claude (não esta
conversa) para a parte analítica.

## Primeiro, o limite real — leia antes do resto

**Eu não consigo deixar isso rodando de forma persistente.** Meu ambiente
de trabalho (onde rodei e testei tudo neste projeto) é um sandbox que reseta
a cada tarefa — não existe Docker Engine instalado nele, e nada que eu
"ligue" aqui continua no ar depois que a conversa termina. Então:

- Eu escrevi o código da aplicação inteira (abaixo).
- Eu **não** consegui rodar `docker build` / `docker run` de verdade — sem
  Docker no sandbox, não tem como provar isso aqui.
- Eu **não** tenho credenciais reais de Mixpanel Service Account, Notion
  Integration ou Anthropic API Key — não testei nenhuma chamada de API
  contra os serviços reais.
- Fazer isso rodar de fato exige infraestrutura fora do meu alcance: alguém
  (você, ou o Vini) precisa gerar as credenciais, provisionar onde o
  container vai rodar (servidor próprio, VM na nuvem, o que a Predialize já
  usa) e subir o container lá.

## O que está provado, e como

| Camada | Status | Como testei |
|---|---|---|
| Template Jinja2 + gerador (`dashboard_template.html.j2`) | **Provado** | Já validado visualmente em rodadas anteriores deste projeto — reaproveitado sem mudança de lógica |
| Estrutura da aplicação FastAPI (`main.py`, rotas, tratamento de erro) | **Provado, sem Docker** | Rodei com `TestClient` no sandbox: `GET /saude` responde 200; `POST /paineis/Rogga` sem credenciais falha de forma controlada (500 com mensagem clara, não um stack trace cru) |
| Import de todos os módulos (`mixpanel_client`, `notion_client`, `claude_client`, `generator`) | **Provado** | Todos importam sem erro de sintaxe/estrutura |
| Chamada real à Mixpanel Query API | **Não testado** | Sem credenciais de Service Account |
| Chamada real à Notion API | **Não testado** | Sem Integration Token próprio |
| Chamada real à API da Claude | **Não testado** | Sem Anthropic API Key |
| `docker build` / `docker run` | **Não testado** | Sem Docker Engine no sandbox |

## Achado importante descoberto ao escrever isso: risco no JQL do Mixpanel

O JQL (a forma de fazer consulta customizada no Mixpanel, usada pra réplicar
o que eu fazia manualmente — funil, frequência, breakdown por Enterprise)
está em **"maintenance mode"**. A documentação da própria Mixpanel chegou a
anunciar desligamento completo em 31/dez/2025 e depois **removeu essa data**
de uma versão mais recente da doc — o que sugere que não desligaram como
planejado, mas não há garantia de que continua funcionando, nem por quanto
tempo. **Antes de depender disso pra qualquer coisa importante, o primeiro
passo com credenciais reais precisa ser confirmar que o endpoint JQL ainda
responde.** Se não responder, o caminho vira: salvar os relatórios Insights
equivalentes na UI do Mixpanel (a Predialize já tem alguns — "Acessos no Mês
(MAU)", por exemplo) e consultar por `bookmark_id`, que é o método que a
própria Mixpanel recomenda e não corre esse risco.

## O que a "inteligência" faz aqui — e o que não faz

`claude_client.py` chama a API da Claude pra gerar exatamente a parte que
ficou marcada como manual o projeto inteiro: a observação analítica de cada
empreendimento e a leitura por segmento — usando os mesmos princípios que
apliquei aqui à mão (nunca misturar cadastro pendente em médias, não inventar
taxa sobre amostra pequena, não citar nome de funcionário interno). A Claude
**não** decide o que consultar nem calcula as métricas — isso continua sendo
Mixpanel (uso) + Notion (cadastro) + aritmética simples no `generator.py`.
É opcional: a rota só chama a Claude se `usar_claude=true` for passado.

## Escopo declarado — o que ficou de fora, de propósito

- `mixpanel_client.py` implementa a consulta central (usuários únicos por
  empreendimento). Funil, frequência de acesso, funcionalidades mais
  usadas, sistema operacional e top 10 usuários seguem exatamente o mesmo
  padrão (JQL com join Events+People, ou um Insights salvo) — não escrevi
  as 5 consultas restantes porque é repetição mecânica do mesmo padrão, não
  uma decisão nova, e cada uma multiplicaria a superfície não testada sem
  agregar dúvida de arquitetura.
- Tendência mensal (série de 14 meses) também não está implementada —
  mesma razão: é a mesma consulta com `unit: "month"`, já demonstrada no
  `mixpanel_client.py` original usado durante o projeto.

## Como rodar (quando tiver onde rodar)

```bash
cp .env.example .env
# preencher .env com as credenciais reais
docker compose up --build
curl -X POST "http://localhost:8000/paineis/Rogga?from_date=2025-06-01&to_date=2026-07-31&usar_claude=true"
```

## Estrutura

```
dashboard-service/
  app/
    mixpanel_client.py   # Mixpanel Query API (Service Account)
    notion_client.py     # Notion API (Integration própria)
    claude_client.py     # Anthropic Messages API
    generator.py          # orquestra os três + Jinja2
    templates/
      dashboard_template.html.j2
  main.py                 # FastAPI
  Dockerfile
  docker-compose.yml
  requirements.txt
  .env.example
```

# AI Chatbot com RAG

Pipeline completo de IA conversacional com RAG: API para chat, ingestao de documentos, ingestao web por scraping, banco vetorial para recuperacao de contexto e orquestracao via n8n.

## 🎯 Objetivo do projeto

Este projeto resolve um problema comum em produtos de IA: responder perguntas com contexto real da sua base (arquivos e web), sem depender apenas do conhecimento generico do modelo.

Voce pode usar esta base para:
- atendimento interno com base em documentos
- assistente para equipes de operacao/comercial/suporte
- prototipo de produto SaaS com IA local

## 🧩 Visao dos modulos

O repositorio foi organizado em blocos claros para facilitar manutencao e escalabilidade:

- API (`api/`): recebe perguntas, processa arquivos, chama RAG e retorna resposta
- Banco (`PostgreSQL + pgvector`): guarda embeddings e historico de conversa
- LLM (`Ollama`): gera respostas localmente
- Automacao (`n8n`): integra canais/fluxos externos com a API
- Infra (`docker-compose.yml`): sobe tudo com um comando

## 🛠️ Tecnologias usadas (e por que)

- Python 3.11: ecossistema maduro para IA, scraping e APIs
- Litestar: framework rapido e moderno para APIs async
- PostgreSQL: banco robusto, conhecido e confiavel em producao
- pgvector: adiciona busca vetorial no proprio PostgreSQL
- Ollama: executa modelos locais, reduzindo custo e dependencia externa
- Docker Compose: ambiente reproduzivel para dev e testes
- n8n: automacao low-code para integrar chatbot com workflows

Resumo estrategico da stack:
- menor custo operacional (LLM local)
- menor complexidade de infraestrutura (Postgres + pgvector no mesmo banco)
- onboarding rapido para novos devs (docker compose up)

## 🚀 Quick Start

Pre-requisitos:
- Docker Desktop
- 8 GB RAM (recomendado para Ollama)

Configurar ambiente:

```bash
cp .env.example .env
```

No PowerShell:

```powershell
Copy-Item .env.example .env
```

Subir tudo:

```bash
docker compose up -d --build
```

Observacao importante:
- no startup da API, o sistema tenta ingerir automaticamente a URL configurada em `SCRAPE_URL`
- se a URL ja estiver indexada, o cache evita retrabalho

Health check:

```bash
curl http://localhost:8000/health
```

Resposta esperada:

```json
{
  "status": "healthy",
  "service": "chatbot-api",
  "version": "1.0.0"
}
```

## 🏗️ Arquitetura

```text
n8n (5678)
  -> API Litestar (8000)
      -> Ollama (11434)
      -> PostgreSQL + pgvector (5432)
```

Fluxo logico:
- usuario envia pergunta (com ou sem arquivo)
- API processa entrada e recupera contexto relevante
- modelo gera resposta usando contexto recuperado
- historico e documentos ficam persistidos no banco

## 🔌 Endpoints principais

### POST /chat

Importante: o endpoint recebe `multipart/form-data`.

Pergunta sem arquivo:

```bash
curl -X POST http://localhost:8000/chat \
  -F "question=O que e RAG?" \
  -F "session_id=minha-sessao"
```

Pergunta com arquivo:

```bash
curl -X POST http://localhost:8000/chat \
  -F "question=Resuma o arquivo" \
  -F "session_id=minha-sessao" \
  -F "file=@./exemplo.pdf"
```

Exemplo de resposta:

```json
{
  "response": "...",
  "session_id": "minha-sessao",
  "timestamp": "2026-03-18T00:00:00.000000",
  "sources": null
}
```

### POST /scrape

Ingere uma URL no banco para depois ser usada no RAG.

```bash
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"http://neverssl.com"}'
```

Comportamento atual do endpoint:
- faz cache por URL (reaproveita conteudo ja indexado)
- extrai e trunca texto grande para manter performance
- inicia indexacao de embeddings em background
- retorna sucesso rapidamente, sem bloquear ate o embedding terminar

Exemplo de resposta atual da API:

```json
{
  "status": "success",
  "message": "Scraping concluido; indexacao de embeddings iniciada em background",
  "documents_count": 1,
  "timestamp": "2026-03-18T00:00:00.000000"
}
```

### GET /health

```bash
curl http://localhost:8000/health
```

## 📁 Estrutura do backend

```text
api/
  app.py
  config.py
  models.py
  exceptions.py
  logger.py
  database/connection.py
  routes/chat.py
  routes/scrape.py
  services/rag.py
  services/embeddings.py
  services/file_parser.py
```

Pontos importantes da organizacao:
- `routes/`: entrada HTTP da aplicacao
- `services/`: regras de negocio (RAG, embeddings, parser)
- `database/`: conexao e operacoes de persistencia

## ⚙️ Configuracao (.env)

Valores comuns (defaults do codigo):

Use `.env.example` como base para criar seu `.env` local.

```env
DB_HOST=postgres
DB_PORT=5432
DB_NAME=chatbot
DB_USER=postgres
DB_PASSWORD=postgres

OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=llama3

API_PORT=8000
DEBUG=false
LOG_LEVEL=INFO

SCRAPE_TIMEOUT=30
SCRAPE_URL=https://pt.wikipedia.org/wiki/Intelig%C3%AAncia_artificial
```

## 🗄️ Banco de dados

Schema atual criado em startup:

Tabela `documents`:
- id SERIAL PRIMARY KEY
- content TEXT NOT NULL
- metadata JSONB
- embedding vector(4096)
- created_at, updated_at

Tabela `chat_history`:
- id SERIAL PRIMARY KEY
- session_id VARCHAR(255)
- question TEXT
- answer TEXT
- sources TEXT
- created_at

Observacao: o indice ivfflat foi desativado no init para evitar erro com embedding(4096) em versoes que limitam dimensao.

## 🔄 Integracao n8n

Este projeto utiliza o n8n como camada de orquestração e interface de interação

### O que e o n8n

n8n e uma plataforma de automacao low-code, open-source, com interface visual de fluxos (nodes). Permite conectar servicos, criar workflows e processar dados sem escrever muito codigo.

No contexto deste projeto, o n8n atua como a camada de orquestracao: é responsável por receber a mensagem do usuário, processa a mensagem e define o fluxo de execução e chama a API.

### Por que foi usado aqui

- Separa a camada de canal (interface de chat) da logica de negocio (API)
- Permite troca de canal facilmente (chat embutido, WhatsApp, Telegram, Slack etc.) sem mudar a API
- Facilita decisoes condicionais no fluxo (ex.: mensagem com ou sem arquivo, mensagem com URL para scraping)
- Reduz codigo de "plumbing": condicoes, formatacao de campos e roteamento ficam no fluxo visual

### Como o n8n se conecta a este projeto

O n8n roda no container `n8n` (porta 5678) e se comunica com a API pelo nome de servico Docker (`http://api:8000`).

Fluxo principal implementado:

```text
[Usuario escreve no chat]
        |
[When chat message received]   <- trigger do n8n
        |
[Code]                         <- normaliza campos da mensagem
        |
[IF]                           <- tem arquivo anexo?
   |              |
[HTTP Request]  [HTTP Request] <- POST /chat com ou sem arquivo
        |
[Code]                         <- formata resposta
        |
[Chat > Send a message]        <- devolve resposta ao usuario
```

Fluxo opcional (mensagem com link aciona scraping):

```text
[When chat message received]
        |
[IF]   <- mensagem contem http:// ou https://?
   |              |
[POST /scrape]  [direto para /chat]
        |
[POST /chat]
```

### Acesso a interface

Apos subir o docker compose, acesse:

```
http://localhost:5678
```

O workflow completo com instrucoes de configuracao de cada node esta em `N8N_WORKFLOW.md`.

## ✅ Testes

```bash
docker compose exec -T api pytest test_api.py -v
```

## 🧯 Troubleshooting

- Erro de rede no /scrape (Network is unreachable): geralmente intermitencia externa do container. Tente novamente com outra URL HTTP para validar rapidamente.
- Erro SSL no /scrape (CERTIFICATE_VERIFY_FAILED): problema de CA no container ao acessar HTTPS.
- Comando curl nao encontrado (exit 127): use PowerShell `Invoke-RestMethod` ou teste via Python dentro do container.

Exemplos uteis:

```bash
# logs da API
docker compose logs -f api

# testar scrape de dentro do container
docker compose exec -T api python -c "import requests; print(requests.get('http://neverssl.com', timeout=10).status_code)"

# verificar historico salvo
docker compose exec -T postgres psql -U postgres -d chatbot -c "SELECT COUNT(*) FROM chat_history;"
```

## 🌟 Features

- Chat com historico por session_id
- Prioridade de contexto: arquivo da requisicao -> documento mais recente da sessao -> RAG global
- Upload de PDF, CSV e Excel
- Scrape de URL para ingestao em RAG (com cache e indexacao em background)
- Ingestao automatica da `SCRAPE_URL` no startup da API
- Embeddings 4096-dim com busca vetorial
- LLM local com Ollama

Versao 1.0.0 - Marco 2026

# PDV Caixa Diário

Sistema de Ponto de Venda (PDV) para controle de caixa diário, desenvolvido com FastAPI, SQLModel, HTMX e Tailwind CSS.

## Funcionalidades

- **Autenticação**: Login com sessões seguras (admin/operator)
- **Controle de Caixa**: Abertura, fechamento e comprovantes
- **Lançamento de Vendas**: Interface rápida com HTMX, suporte a múltiplas formas de pagamento
- **Cancelamento de Vendas**: Apenas admin, com motivo e confirmação de senha
- **Relatórios**: Filtros por período, KPIs (total, média diária, ticket médio), totais por forma de pagamento
- **Auditoria**: Registro de operações sensíveis (cancelamentos, fechamentos)
- **Gestão de Usuários**: CRUD de operadores (somente admin)

## Tecnologias

- **Backend**: FastAPI 0.115.0, SQLModel 0.0.21, Uvicorn
- **Frontend**: Jinja2, HTMX 1.9.10, Tailwind CSS, Flowbite
- **Banco de Dados**: SQLite (padrão), facilmente adaptável para PostgreSQL/MySQL
- **Autenticação**: Starlette Sessions + Passlib (pbkdf2_sha256)

## Setup Local

### Pré-requisitos
- Python 3.13+ (ou 3.11+)
- pip

### Instalação

1. Clone o repositório:
   ```bash
   git clone https://github.com/seu-usuario/pdv.git
   cd pdv
   ```

2. Crie e ative um ambiente virtual:
   ```bash
   python -m venv .venv
   # Windows
   .\.venv\Scripts\activate
   # Linux/Mac
   source .venv/bin/activate
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure variáveis de ambiente (opcional, há fallback):
   ```bash
   cp .env.example .env
   # Edite .env e defina SECRET_KEY com uma chave forte
   ```

5. Inicie o servidor:
   ```bash
   uvicorn app.main:app --reload
   ```

6. Acesse: `http://localhost:8000`

### Usuário padrão
- **Username**: `admin`
- **Senha**: `admin123`

**⚠️ IMPORTANTE**: Altere a senha padrão após o primeiro acesso!

## Deploy com Docker (Portainer)

### Build e execução local

```bash
docker-compose up -d
```

Acesse: `http://localhost:8000`

### Deploy via Portainer (Git Repository)

**Método recomendado para VPS com Portainer:**

1. Faça push do projeto para seu repositório GitHub/GitLab
2. No Portainer, vá em **Stacks** > **Add Stack**
3. Selecione **Repository** (aba)
4. Configure:
   - **Repository URL**: `https://github.com/seu-usuario/pdv.git`
   - **Repository reference**: `refs/heads/main` (ou sua branch)
   - **Compose path**: `docker-compose.yml`
   - **Authentication**: Se repositório privado, adicione credenciais
5. Em **Environment variables**, adicione:
   ```
   SECRET_KEY=<sua-chave-gerada-com-openssl-rand-hex-32>
   ```
6. Clique em **Deploy the stack**
7. Aguarde o build e acesse via `http://seu-servidor:8000`

**Atualizações futuras:**
- No Portainer, vá na stack criada
- Clique em **Pull and redeploy** para atualizar do repositório

### Deploy via Portainer (Upload manual)

1. No Portainer, vá em **Stacks** > **Add Stack**
2. Cole o conteúdo do `docker-compose.yml`
3. Configure a variável de ambiente:
   - `SECRET_KEY`: gere uma chave forte (ex: `openssl rand -hex 32`)
4. Clique em **Deploy the stack**

O volume `pdv_data` persiste o banco SQLite entre restarts.

### Stack em Docker Swarm (com Traefik)

Se seu ambiente no Portainer usa Swarm (como no exemplo do Chatwoot), utilize o arquivo `docker-compose.swarm.yml`:

1. Publique a imagem do PDV em um registry (Docker Hub/GHCR) ou ajuste o campo `image:` no arquivo para sua imagem.
2. No Portainer, vá em Stacks → Add Stack → Repository e aponte para este repositório.
3. Em Compose path, informe: `docker-compose.swarm.yml`.
4. Defina as variáveis de ambiente na stack:
   - `SECRET_KEY` (obrigatório)
   - `TRAEFIK_HOST` (seu domínio, ex. pdv.seudominio.com)
   - `TRAEFIK_NETWORK` (rede externa do Traefik, ex. network_swarm_public)
   - `TRAEFIK_CERTRESOLVER` (ex. letsencrypt)
   - `TRAEFIK_ENTRYPOINTS` (ex. websecure)
5. Deploy the stack. O Traefik fará o roteamento HTTPS para a porta interna 8000.

Observações:
- Em Swarm, `build:` não é suportado pela stack do Portainer; use uma imagem publicada.
- Não é necessário mapear portas (Traefik fará o roteamento pela rede externa).

### CI/CD: publicar imagem automaticamente (Docker Hub)

Este repositório inclui um workflow do GitHub Actions em `.github/workflows/docker-publish.yml` que:

- builda a imagem do PDV
- publica no Docker Hub com tags `latest` e `sha`

Como ativar:
1. Crie um token (Access Token) no Docker Hub
2. No GitHub → Settings → Secrets and variables → Actions → New repository secret
   - `DOCKERHUB_USERNAME` = seu usuário do Docker Hub
   - `DOCKERHUB_TOKEN` = o token gerado
3. Faça um push para a branch `main` (ou rode manualmente em Actions)
4. Ajuste a imagem no `docker-compose.swarm.yml` para `docker.io/SEU_USUARIO/pdv-caixa:latest` (se diferente)
5. No Portainer (Swarm), use `docker-compose.swarm.yml` como Compose path e faça o deploy.

### Usando Traefik (Domínio + HTTPS)

Se você já tem o Traefik rodando na sua VPS, pode publicar o PDV diretamente no seu domínio pela própria stack:

1. Garanta que o Traefik e sua rede externa existam (por exemplo, `traefik_proxy`).
2. No Portainer, ao criar/editar a stack, adicione as variáveis de ambiente:
   - `TRAEFIK_HOST` = `pdv.seudominio.com`
   - `TRAEFIK_NETWORK` = `traefik_proxy` (ou o nome da sua rede)
   - `TRAEFIK_CERTRESOLVER` = `letsencrypt` (ou o que você configurou no Traefik)
   - `TRAEFIK_ENTRYPOINTS` = `websecure`
3. A stack já possui labels do Traefik e se conecta automaticamente à rede externa definida.
4. Certifique-se que seu domínio aponta (DNS) para o IP da VPS.

Observações:
- Mantivemos a porta `8000:8000` mapeada para testes locais. Em produção via Traefik, ela pode permanecer sem conflito.
- O serviço interno escuta na porta 8000; Traefik encaminha via `traefik.http.services.pdv.loadbalancer.server.port=8000`.

### Configuração de produção

- **SECRET_KEY**: defina uma chave forte e única
- **HTTPS**: use um proxy reverso (Nginx, Traefik, Caddy) com certificado SSL
   - Para Traefik, utilize as variáveis `TRAEFIK_*` na stack (veja a seção "Usando Traefik")
- **Backup**: configure backup regular do volume `pdv_data`
- **Logs**: considere integrar com sistema de logs centralizado

## Estrutura do Projeto

```
pdv/
├── app/
│   ├── main.py              # Aplicação FastAPI
│   ├── db.py                # Configuração do banco
│   ├── models.py            # Modelos SQLModel
│   ├── deps.py              # Dependências (autenticação, CSRF)
│   ├── utils.py             # Funções auxiliares
│   ├── routers/             # Rotas da aplicação
│   │   ├── auth.py
│   │   ├── cash.py
│   │   ├── sales.py
│   │   ├── reports.py
│   │   ├── admin.py
│   │   └── audit.py
│   └── templates/           # Templates Jinja2
├── tools/                   # Scripts auxiliares
│   └── clear_sales.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## Segurança

- **Autenticação**: Todas as páginas (exceto login) exigem autenticação
- **CSRF Protection**: Token CSRF em todos os formulários
- **Senhas**: Hash seguro com pbkdf2_sha256
- **Cancelamentos**: Revalidação de senha do admin
- **Auditoria**: Registro de operações sensíveis

## API Endpoints

### Públicas
- `GET /entrar` - Página de login
- `POST /entrar` - Autenticação

### Autenticadas
- `GET /painel` - Redireciona para relatórios (página principal)
- `GET /caixa/status` - Status do caixa
- `GET /caixa/abrir` - Abrir caixa
- `POST /caixa/fechar` - Fechar caixa
- `GET /vendas/nova` - Lançar venda
- `POST /vendas/cancelar/{id}` - Cancelar venda (admin)
- `GET /relatorios` - Relatórios com filtros
- `GET /administracao/usuarios` - Gestão de usuários (admin)

## Desenvolvimento

### Executar testes
```bash
pytest
```

### Linting e formatação
```bash
ruff check . --fix
mypy .
```

### Limpar dados de teste
```bash
python tools/clear_sales.py
```

## Licença

MIT License - veja LICENSE para detalhes.

## Suporte

Para dúvidas ou problemas, abra uma issue no GitHub.

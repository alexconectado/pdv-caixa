# Deploy PDV no Portainer via Git

Este guia mostra como fazer o deploy do PDV Caixa Diário no Portainer usando repositório Git.

## Pré-requisitos

- VPS com Docker e Portainer instalados
- Repositório Git (GitHub, GitLab, etc.)
- Acesso ao Portainer via web

## Passo a passo

### 1. Prepare o repositório

```bash
# No seu computador local, dentro da pasta do projeto
git init
git add .
git commit -m "feat: PDV Caixa Diário - sistema completo"
git branch -M main

# Adicione o remote do seu repositório
git remote add origin https://github.com/seu-usuario/pdv.git

# Faça o push
git push -u origin main
```

### 2. Deploy no Portainer

1. Acesse o Portainer: `http://seu-servidor:9000`
2. Vá em **Stacks** > **Add Stack**
3. Dê um nome: `pdv-caixa`
4. Selecione a aba **Repository**
5. Preencha:
   - **Repository URL**: `https://github.com/seu-usuario/pdv.git`
   - **Repository reference**: `refs/heads/main`
   - **Compose path**: `docker-compose.yml`
   - **Authentication**: Marque se o repositório for privado e adicione token/senha

6. Em **Environment variables**, clique em **+ add environment variable**:
   - **name**: `SECRET_KEY`
   - **value**: Gere uma chave com `openssl rand -hex 32` no terminal

7. Clique em **Deploy the stack**

### 3. Aguarde o build

- O Portainer vai clonar o repositório
- Fazer o build da imagem Docker
- Criar o volume `pdv_data`
- Iniciar o container

Acompanhe os logs na aba **Logs** da stack.

### 4. Acesse a aplicação

Abra no navegador: `http://seu-servidor:8000`

**Login padrão:**
- Usuário: `admin`
- Senha: `admin123`

⚠️ **Altere a senha imediatamente após o primeiro login!**

## Atualizações futuras

Quando você fizer alterações no código:

1. Commit e push para o repositório:
   ```bash
   git add .
   git commit -m "feat: nova funcionalidade"
   git push
   ```

2. No Portainer, vá na stack `pdv-caixa`
3. Clique em **Pull and redeploy**
4. Aguarde a atualização

## Configurações adicionais

### Proxy reverso (Traefik recomendado)

Se você já usa Traefik no seu servidor, a stack já vem pronta com labels e rede externa. No Portainer, defina as variáveis de ambiente:

- `TRAEFIK_HOST` = `pdv.seudominio.com`
- `TRAEFIK_NETWORK` = `traefik_proxy` (ou o nome da sua rede do Traefik)
- `TRAEFIK_CERTRESOLVER` = `letsencrypt` (ou seu resolver)
- `TRAEFIK_ENTRYPOINTS` = `websecure`

Certifique-se de que o Traefik está publicado com o provider Docker e que a rede externa existe (ex.: `traefik_proxy`). A stack se conectará a essa rede automaticamente.

### Backup do banco de dados

O banco SQLite está no volume `pdv_data`. Para backup:

```bash
# Encontre o path do volume
docker volume inspect pdv_data

# Copie o arquivo pdv.db
docker cp pdv_app:/data/pdv.db ./backup_pdv_$(date +%Y%m%d).db
```

Configure um cronjob para backup automático.

### Logs

Ver logs do container:
```bash
docker logs -f pdv_app
```

Ou via Portainer: **Containers** > `pdv_app` > **Logs**

## Troubleshooting

### Container não inicia
- Verifique os logs no Portainer
- Confirme que a porta 8000 não está em uso
- Valide o SECRET_KEY nas variáveis de ambiente

### Erro de permissão no volume
```bash
docker exec pdv_app chmod 777 /data
```

### Resetar banco de dados
```bash
docker exec pdv_app rm /data/pdv.db
docker restart pdv_app
```

Isso recriará o banco com o admin padrão.

## Suporte

Problemas? Abra uma issue no repositório GitHub.

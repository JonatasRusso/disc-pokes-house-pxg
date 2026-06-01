# Como Rodar

## 1. Configurar o .env

Copie `.env.example` para `.env` e preencha:

```
DISCORD_TOKEN=         # Bot token do Discord Developer Portal
DISCORD_CLIENT_ID=     # Application ID
DISCORD_CLIENT_SECRET= # OAuth2 Secret
DISCORD_GUILD_ID=      # ID do seu servidor
DISCORD_NOTIFY_CHANNEL_ID= # Canal onde o bot pinga horários
DISCORD_POKEMON_CHANNEL_ID= # Canal de pokémons
JWT_SECRET=            # Qualquer string aleatória longa
SITE_URL=http://localhost:5173
API_URL=http://localhost:8000
DATABASE_URL=sqlite+aiosqlite:///./discbot.db
```

## 2. No Discord Developer Portal

- Em **OAuth2 → Redirects**: adicione `http://localhost:8000/auth/callback`
- Em **Bot → Privileged Gateway Intents**: ative `Server Members Intent` e `Message Content Intent`
- Convide o bot com scopes: `bot` + `applications.commands`
- Permissões necessárias: `Send Messages`, `Add Reactions`, `Read Message History`, `Manage Messages`

## 3. Rodar o backend (API + bot juntos)

```bash
# Terminal 1 — API
python -m uvicorn api.main:app --reload --port 8000

# Terminal 2 — Bot
python -m bot.main
```

## 4. Rodar o frontend

```bash
cd frontend
npm run dev
# Acesse http://localhost:5173
```

## 5. Primeiro admin

No Discord, o dono do servidor usa:
```
/admin @usuario Conceder
```

## 6. Cadastrar pokémons

Via API (ou criar endpoint admin no site):
```bash
curl -X POST http://localhost:8000/pokemon \
  -H "Content-Type: application/json" \
  -d '{"name":"Pikachu","category":"A","image_url":"https://..."}'
```

## 7. Deploy no Railway

1. Suba o código para um repositório GitHub
2. Crie um projeto no Railway, conecte o repo
3. Adicione um banco PostgreSQL no Railway
4. Configure as variáveis de ambiente (substitua `DATABASE_URL` pela URL do Postgres)
5. Para o frontend: deploy no Vercel apontando para a pasta `frontend/`

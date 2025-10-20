# Bike Tracker Alerts System - Frontend + Gmail IMAP

Sistema simplificado para rastrear bikes via alertas do Gmail IMAP. Frontend processaos dados localmente, sem database.

## 🎯 Funcionalidades

- ✅ **Sincronização Gmail IMAP**: Conecta-se diretamente ao Gmail para buscar alertas
- ✅ **Frontend Completo**: Interface React com shadcn/ui para visualização de alertas e bikes
- ✅ **Sem Database**: Dados armazenados em cache de memória no backend
- ✅ **Sem Autenticação**: Sistema simplificado sem login/JWT
- ✅ **Categorização de Alertas**: Filtragem por tipo (Light Sensor, Over-turn, Heavy Impact, etc.)

## 📁 Estrutura

```
/app/
├── backend/
│   ├── server.py          # FastAPI minimalista (Gmail IMAP only)
│   ├── requirements.txt   # Apenas fastapi, uvicorn, dotenv
│   └── .env               # Credenciais Gmail (opcional)
├── frontend/
│   ├── src/
│   │   ├── App.js         # Interface principal
│   │   └── components/ui/ # shadcn/ui components
│   └── package.json
└── README.md
```

## 🚀 Como Usar

### 1. Backend (Gmail IMAP)

```bash
cd /app/backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

**Configurar Gmail via API:**
```bash
curl -X POST http://localhost:8001/api/gmail/configure \
  -H "Content-Type: application/json" \
  -d '{"email": "seu@gmail.com", "app_password": "sua_senha_app"}'
```

**Sincronizar emails:**
```bash
curl -X POST http://localhost:8001/api/gmail/sync \
  -H "Content-Type: application/json" \
  -d '{"limit": 100}'
```

### 2. Frontend

```bash
cd /app/frontend
yarn install
yarn start
```

Acesse: `http://localhost:3000`

## 🔧 Configuração Gmail

1. Ative **"Acesso de apps menos seguros"** ou crie uma **Senha de App** no Gmail
2. Configure via API `/api/gmail/configure` ou defina no `.env`:
   ```
   GMAIL_EMAIL=seu@gmail.com
   GMAIL_APP_PASSWORD=sua_senha_app
   ```

## 📡 API Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/gmail/configure` | Configura credenciais Gmail |
| POST | `/api/gmail/sync` | Sincroniza emails do Gmail |
| GET | `/api/alerts/list` | Lista alerts em cache |
| GET | `/api/alerts/categories` | Categorias de alertas |
| GET | `/api/bikes/list` | Lista bikes (agrupadas por tracker_name) |
| DELETE | `/api/alerts/clear-all` | Limpa cache de alerts |
| GET | `/api/health` | Status do sistema |

## 🎨 Frontend

- **React 19** + **shadcn/ui**
- **Tailwind CSS** para styling
- **Axios** para chamadas API
- **date-fns** para manipulação de datas
- **react-day-picker** para date range picker

## 🗑️ O que foi removido

❌ **Backend:**
- PostgreSQL/Neon database
- Autenticação JWT
- User management
- Cookies de sessão

❌ **Arquivos:**
- `netlify.toml`
- `vercel.json`
- `tests/`
- `scripts/`
- Deployment configs

❌ **Frontend libs:**
- `react-datepicker`
- `next-themes`

## 📝 Notas

- Dados são armazenados **apenas em memória** no backend
- Ao reiniciar o backend, cache é perdido
- Para dados persistentes, re-sincronize via `/api/gmail/sync`
- Gmail IMAP funciona 100% como antes, apenas sem database

## 🐛 Troubleshooting

**Backend não inicia:**
```bash
tail -n 50 /var/log/supervisor/backend.*.log
```

**Gmail IMAP falha:**
- Verifique credenciais
- Ative "Acesso de apps menos seguros"
- Use senha de app do Google

**Frontend não carrega dados:**
- Verifique se backend está rodando: `http://localhost:8001/api/health`
- Sincronize emails primeiro: `/api/gmail/sync`

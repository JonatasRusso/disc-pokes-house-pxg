#!/bin/bash
# Aplica migrações (Alembic) e sobe a API FastAPI + o bot Discord em paralelo.
# init_db() ainda roda create_all como rede de segurança em dev/banco novo.
alembic upgrade head
uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} &
python -m bot.main

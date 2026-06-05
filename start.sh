#!/bin/bash
# Sobe a API FastAPI e o bot Discord em paralelo
uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} &
python -m bot.main

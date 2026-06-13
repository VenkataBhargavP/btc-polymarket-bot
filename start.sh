#!/bin/bash
set -e

echo "Installing Python dependencies..."
pip install -r requirements.txt --quiet

echo "Building frontend..."
cd frontend && npm install --silent && npm run build && cd ..

echo "Starting bot..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 &

echo "Bot running → http://localhost:8000"
wait

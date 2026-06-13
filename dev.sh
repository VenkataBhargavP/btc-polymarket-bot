#!/bin/bash
trap 'kill %1 %2 2>/dev/null' EXIT

echo "Starting backend (hot reload)..."
uvicorn backend.main:app --reload --port 8000 &

echo "Starting frontend dev server..."
cd frontend && npm run dev -- --port 5173 &

echo "Backend → http://localhost:8000"
echo "Frontend → http://localhost:5173"
wait

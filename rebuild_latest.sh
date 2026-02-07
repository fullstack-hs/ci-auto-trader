#!/bin/bash
set -e

echo "🚀 Starting deployment..."

echo "⬇️ Executing git pull --rebase..."
git pull --rebase

echo "🔨 Building Docker image..."
docker build -t auto-trader:latest .

echo "🛑 Removing old container..."
docker rm -f auto-trader 2>/dev/null || true

echo "▶️ Starting new container..."
docker run -d \
  --name auto-trader \
  --restart unless-stopped \
  auto-trader:latest

echo "✅ Deployment finished successfully!"
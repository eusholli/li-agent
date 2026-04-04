#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "Deploying li-article-api to production..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
echo "Deployment complete. API available at https://$(grep ^DOMAIN .env | cut -d= -f2)"

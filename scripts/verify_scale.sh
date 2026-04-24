#!/bin/bash
set -e

echo "=== Scale backend to 2 instances ==="
docker compose up -d --scale backend=2
sleep 20

echo "=== Check both backend instances exist ==="
docker compose ps backend

echo "=== Check leader election log ==="
docker compose logs backend 2>&1 | grep -E "(simulation leader|is a follower)" | head -5

echo "=== Check one instance is leader, one is follower ==="
LEADER_COUNT=$(docker compose logs backend 2>&1 | grep -c "is the simulation leader" || true)
FOLLOWER_COUNT=$(docker compose logs backend 2>&1 | grep -c "is a follower" || true)
echo "Leaders: $LEADER_COUNT, Followers: $FOLLOWER_COUNT"
[[ $LEADER_COUNT -eq 1 ]] || { echo "FAIL: expected 1 leader"; exit 1; }
[[ $FOLLOWER_COUNT -eq 1 ]] || { echo "FAIL: expected 1 follower"; exit 1; }

echo "=== Check Redis has leader key ==="
docker compose exec -T redis redis-cli GET drone_platform:simulation_leader

echo "=== Check health endpoint via nginx (round-robin) ==="
for i in 1 2 3 4; do
  curl -s http://localhost:8000/health | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])"
done

echo "=== All checks passed ==="

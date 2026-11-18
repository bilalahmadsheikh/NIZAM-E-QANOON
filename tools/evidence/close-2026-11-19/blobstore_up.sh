#!/usr/bin/env bash
# The compose service itself, end to end: start under the profile, wait healthy, S3 round trip with infra/.env creds.
cd /mnt/e/Nizam_e_Qanoon; set -a; . infra/.env; set +a
docker compose -f infra/compose.yaml --profile blobstore up -d blobstore 2>&1 | tail -2
for i in $(seq 1 40); do h=$(docker inspect -f '{{.State.Health.Status}}' nizam-blobstore 2>/dev/null); [ "$h" = healthy ] && break; sleep 3; done
echo "health: $h"
P=${MINIO_PORT:-9000}; A=(--aws-sigv4 "aws:amz:us-east-1:s3" --user "$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD" -s)
echo "create: $(curl "${A[@]}" -o /dev/null -w '%{http_code}' -X PUT http://127.0.0.1:$P/nizam-selftest)"
echo "put:    $(echo ok | curl "${A[@]}" -o /dev/null -w '%{http_code}' -X PUT --data-binary @- http://127.0.0.1:$P/nizam-selftest/x)"
echo "get:    $(curl "${A[@]}" http://127.0.0.1:$P/nizam-selftest/x)"
echo "delete: $(curl "${A[@]}" -o /dev/null -w '%{http_code}' -X DELETE http://127.0.0.1:$P/nizam-selftest/x) $(curl "${A[@]}" -o /dev/null -w '%{http_code}' -X DELETE http://127.0.0.1:$P/nizam-selftest)"
./nz status 2>/dev/null | grep -E "S3 store|blobstore" ; bash infra/scripts/selftest.sh 2>&1 | grep -i -E "blobstore|port 9000"
docker compose -f infra/compose.yaml --profile blobstore stop blobstore 2>&1 | tail -1
docker compose -f infra/compose.yaml --profile blobstore rm -f blobstore 2>&1 | tail -1

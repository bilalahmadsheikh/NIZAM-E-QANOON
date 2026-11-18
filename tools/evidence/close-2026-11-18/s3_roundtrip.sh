#!/usr/bin/env bash
# S3 round trip against the pinned SeaweedFS image, signed SigV4 (as R2 requires), on a scratch port.
set -u
IMG='chrislusf/seaweedfs:4.51@sha256:f7a49e3f3972ebed5be2ed4befa4a0c68eb7bdddba6e692d42729ceb545134b8'
D=$(mktemp -d); KEY=nizamtest; SEC=$(head -c 18 /dev/urandom | base64 | tr -dc A-Za-z0-9)
printf '{"identities":[{"name":"nizam","credentials":[{"accessKey":"%s","secretKey":"%s"}],"actions":["Admin","Read","List","Tagging","Write"]}]}' "$KEY" "$SEC" > $D/s3.json
docker rm -f nzq-s3-test >/dev/null 2>&1
docker run -d --name nzq-s3-test -p 127.0.0.1:18333:8333 -v $D/s3.json:/etc/seaweedfs/s3.json:ro "$IMG" \
  server -dir=/data -s3 -s3.port=8333 -s3.config=/etc/seaweedfs/s3.json >/dev/null
for i in $(seq 1 40); do curl -s -o /dev/null http://127.0.0.1:18333/ && break; sleep 1; done
S=(--aws-sigv4 "aws:amz:us-east-1:s3" --user "$KEY:$SEC" -s -o /dev/null -w "%{http_code}")
echo "unsigned list (must refuse): $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18333/)"
echo "create bucket: $(curl "${S[@]}" -X PUT http://127.0.0.1:18333/nizam-blobs)"
echo "hello law" > $D/obj.txt
echo "put object:    $(curl "${S[@]}" -X PUT --data-binary @$D/obj.txt -H 'Content-Type: text/plain' http://127.0.0.1:18333/nizam-blobs/raw/test.txt)"
echo "get object:    $(curl --aws-sigv4 'aws:amz:us-east-1:s3' --user "$KEY:$SEC" -s http://127.0.0.1:18333/nizam-blobs/raw/test.txt)"
echo "list objects:  $(curl --aws-sigv4 'aws:amz:us-east-1:s3' --user "$KEY:$SEC" -s 'http://127.0.0.1:18333/nizam-blobs?list-type=2' | grep -o '<Key>[^<]*</Key>')"
echo "wrong secret:  $(curl --aws-sigv4 'aws:amz:us-east-1:s3' --user "$KEY:wrong" -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18333/nizam-blobs/raw/test.txt)"
docker rm -f nzq-s3-test >/dev/null; rm -rf $D

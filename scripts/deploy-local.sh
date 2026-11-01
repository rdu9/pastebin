#!/bin/sh
set -e

if ! git diff --quiet HEAD; then
  echo "uncommitted changes found"
  exit 1
fi

TAG=$(git rev-parse --short HEAD)
echo "deploying $TAG"

docker build -t pastebin:$TAG .
k3d image import pastebin:$TAG -c pastebin

sed -i '' "s|newTag: .*|newTag: \"$TAG\"|" \
  k8s/overlays/local/kustomization.yaml \
  k8s/overlays/local/migrate/kustomization.yaml

kubectl delete job migrate -n pastebin --ignore-not-found
kubectl apply -k k8s/overlays/local/migrate
kubectl wait --for=condition=complete job/migrate -n pastebin --timeout=120s

kubectl apply -k k8s/overlays/local
kubectl rollout status deployment/api -n pastebin --timeout=120s
kubectl rollout status deployment/worker -n pastebin --timeout=120s

echo "deployed $TAG"
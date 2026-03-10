#!/usr/bin/env bash
set -e

echo "==> Starting Minikube..."
minikube start --driver=docker

echo "==> Building image into Minikube's Docker..."
eval $(minikube docker-env)
docker build -t mediassist-pro:latest .

echo "==> Creating namespace and secret..."
kubectl apply -f k8s/namespace.yaml
kubectl create secret generic mediassist-secret \
  --from-literal=SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") \
  --from-literal=POSTGRES_PASSWORD=mediassist \
  --namespace=mediassist \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Applying manifests..."
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres-pvc.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/postgres-service.yaml
kubectl apply -f k8s/chroma-pvc.yaml
kubectl apply -f k8s/app-deployment.yaml
kubectl apply -f k8s/app-service.yaml

echo "==> Waiting for app to be ready..."
kubectl rollout status deployment/mediassist-app -n mediassist --timeout=180s

echo "==> Done. Opening service..."
minikube service mediassist-service -n mediassist

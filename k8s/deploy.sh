#!/usr/bin/env bash
# deploy.sh — build images, push to ACR, and deploy to AKS
#
# Usage:
#   ./k8s/deploy.sh
#
# Prerequisites:
#   az login
#   az aks get-credentials --resource-group <RG> --name <CLUSTER>
#
# Required env vars (or edit the defaults below):
#   RESOURCE_GROUP   — Azure resource group (default: nvidia-tracker-rg)
#   AKS_CLUSTER      — AKS cluster name      (default: nvidia-tracker-aks)
#   ACR_NAME         — ACR registry name     (default: nvidiatrackeracr)
#   OPENAI_API_KEY   — OpenAI key to store in the K8s secret

set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-nvidia-tracker-rg}"
AKS_CLUSTER="${AKS_CLUSTER:-nvidia-tracker-aks}"
ACR_NAME="${ACR_NAME:-nvidiatrackeracr}"
ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"
NAMESPACE="nvidia-tracker"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# ── Validate required env var ─────────────────────────────────────────────────
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: OPENAI_API_KEY is not set." >&2
  exit 1
fi

echo "=================================================="
echo "  NVIDIA Tracker — Azure deployment"
echo "  ACR : ${ACR_LOGIN_SERVER}"
echo "  AKS : ${AKS_CLUSTER} (${RESOURCE_GROUP})"
echo "=================================================="

# ── 1. Point kubectl at the cluster ──────────────────────────────────────────
echo ""
echo "[1/7] Fetching AKS credentials..."
az aks get-credentials \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${AKS_CLUSTER}" \
  --overwrite-existing

# ── 2. Create namespace ───────────────────────────────────────────────────────
echo ""
echo "[2/7] Creating namespace '${NAMESPACE}'..."
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# ── 3. Create ACR pull secret ─────────────────────────────────────────────────
echo ""
echo "[3/7] Creating ACR image-pull secret..."
ACR_PASSWORD=$(az acr credential show --name "${ACR_NAME}" --query "passwords[0].value" -o tsv)
kubectl create secret docker-registry acr-pull-secret \
  --namespace "${NAMESPACE}" \
  --docker-server="${ACR_LOGIN_SERVER}" \
  --docker-username="${ACR_NAME}" \
  --docker-password="${ACR_PASSWORD}" \
  --dry-run=client -o yaml | kubectl apply -f -

# ── 4. Create app secrets ─────────────────────────────────────────────────────
echo ""
echo "[4/7] Creating app secrets..."
kubectl create secret generic nvidia-tracker-secrets \
  --namespace "${NAMESPACE}" \
  --from-literal=openai-api-key="${OPENAI_API_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

# ── 5. Build and push orchestrator image via ACR Tasks ───────────────────────
echo ""
echo "[5/7] Building orchestrator image in ACR..."
# Build from repo root so the Dockerfile COPY context works correctly
az acr build \
  --registry "${ACR_NAME}" \
  --image "orchestrator:${IMAGE_TAG}" \
  --file orchestrator/Dockerfile \
  .

# ── 6. Deploy OpenSandbox server ──────────────────────────────────────────────
echo ""
echo "[6/7] Deploying OpenSandbox server..."
kubectl apply -f k8s/opensandbox-server.yaml

echo "  Waiting for OpenSandbox server to be ready..."
kubectl rollout status deployment/opensandbox-server \
  --namespace "${NAMESPACE}" \
  --timeout=120s

# ── 7. Run the orchestrator Job ───────────────────────────────────────────────
echo ""
echo "[7/7] Submitting orchestrator Job..."

# Delete any previous run of the same job so we can resubmit
kubectl delete job nvidia-orchestrator \
  --namespace "${NAMESPACE}" \
  --ignore-not-found

kubectl apply -f k8s/orchestrator-job.yaml

echo ""
echo "  Job submitted. Tailing logs (Ctrl-C when done)..."
kubectl wait --for=condition=ready pod \
  --namespace "${NAMESPACE}" \
  --selector=job-name=nvidia-orchestrator \
  --timeout=120s

kubectl logs \
  --namespace "${NAMESPACE}" \
  --selector=job-name=nvidia-orchestrator \
  --follow

echo ""
echo "=================================================="
echo "  Deployment complete."
echo "=================================================="

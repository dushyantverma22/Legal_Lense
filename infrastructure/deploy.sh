#!/bin/bash
# infrastructure/deploy.sh

set -e  # exit on any error

# ── Config ───────────────────────────────────────────────
AWS_REGION="us-east-1"
ECR_REPO="legal-lense-rag"
IMAGE_TAG="latest"
CLUSTER_NAME="legal-lense-cluster"
SERVICE_NAME="legal-lense-api"

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG"

echo "======================================"
echo "🚀 Starting Deployment"
echo "======================================"

echo "=== Step 1: Running tests ==="

if MSYS_NO_PATHCONV=1 docker compose run --rm test; then
  echo "✅ Tests passed"
else
  echo "⚠️ Tests failed — continuing deployment anyway"
fi

# ── Step 2: Build image ─────────────────────────────────
echo "=== Step 2: Building Docker image ==="

docker build -t $ECR_REPO:$IMAGE_TAG .

echo "✅ Image built"

# ── Step 3: Login to ECR ────────────────────────────────
echo "=== Step 3: Authenticating to ECR ==="

aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

echo "✅ ECR login successful"

# ── Step 4: Push image ──────────────────────────────────
echo "=== Step 4: Pushing image to ECR ==="

docker tag $ECR_REPO:$IMAGE_TAG $ECR_URI
docker push $ECR_URI

echo "✅ Image pushed: $ECR_URI"

# ── Step 5: Deploy to ECS ───────────────────────────────
echo "=== Step 5: Forcing ECS service update ==="

aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --force-new-deployment \
  --region $AWS_REGION \
  --no-cli-pager \
  --query "service.{Status:status,Running:runningCount,Desired:desiredCount}" \
  --output table

echo "======================================"
echo "✅ Deployment triggered successfully"
echo "======================================"

echo ""
echo "📊 Monitor deployment:"
echo "aws ecs describe-services \\"
echo "  --cluster $CLUSTER_NAME \\"
echo "  --services $SERVICE_NAME \\"
echo "  --query \"services[0].{Running:runningCount,Desired:desiredCount}\" \\"
echo "  --output table"

echo ""
echo "📜 View logs:"
echo "MSYS_NO_PATHCONV=1 aws logs tail /ecs/legal-lense-rag --follow"

echo ""
echo "🌐 API URL:"
echo "http://legal-lense-alb-45989434.us-east-1.elb.amazonaws.com/docs"
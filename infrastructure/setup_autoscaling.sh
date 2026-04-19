#!/bin/bash
set -e

AWS_REGION="${AWS_REGION:-us-east-1}"
CLUSTER="legal-lense-cluster"
SERVICE="legal-lense-api"
ALERT_EMAIL="${ALERT_EMAIL:-dushyantvibhu12@gmail.com}"

echo "=== Setting up auto-scaling for $SERVICE ==="

# 1. Register scalable target
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id "service/$CLUSTER/$SERVICE" \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 6 \
  --region $AWS_REGION

# 2. CPU scaling policy
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id "service/$CLUSTER/$SERVICE" \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name "legal-lense-cpu-tracking" \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration \
    '{"TargetValue":60,"PredefinedMetricSpecification":{"PredefinedMetricType":"ECSServiceAverageCPUUtilization"},"ScaleOutCooldown":60,"ScaleInCooldown":900}' \
  --region $AWS_REGION

# 3. Enable Container Insights
aws ecs update-cluster-settings \
  --cluster $CLUSTER \
  --settings name=containerInsights,value=enabled \
  --region $AWS_REGION

# 4. SNS alerts
TOPIC_ARN=$(aws sns create-topic \
  --name legal-lense-scaling-alerts \
  --query "TopicArn" --output text)

aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol email \
  --notification-endpoint "$ALERT_EMAIL"

# 5. Max capacity alarm (FIXED)
aws cloudwatch put-metric-alarm \
  --alarm-name "legal-lense-at-max-capacity" \
  --alarm-description "RAG API at max task count" \
  --namespace AWS/ECS \
  --metric-name RunningTaskCount \
  --dimensions Name=ClusterName,Value=$CLUSTER Name=ServiceName,Value=$SERVICE \
  --statistic Average \
  --period 60 \
  --threshold 6 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 2 \
  --alarm-actions $TOPIC_ARN \
  --region $AWS_REGION

echo ""
echo "=== Auto-scaling setup complete ==="
echo "Check email ($ALERT_EMAIL) to confirm SNS subscription"
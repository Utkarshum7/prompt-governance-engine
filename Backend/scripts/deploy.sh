#!/bin/bash
# Deployment script for AWS ECS

set -e

# Configuration
AWS_REGION="us-east-2"
ECR_REPOSITORY="429441944860.dkr.ecr.us-east-2.amazonaws.com/portkeyaibuilderchallenge"
ECS_CLUSTER="portkey-prompt-parser-cluster"
ECS_SERVICE="portkey-prompt-parser-service"
TASK_DEFINITION="portkey-prompt-parser"
IMAGE_TAG="${1:-latest}"

echo "Starting deployment..."
echo "Region: $AWS_REGION"
echo "Repository: $ECR_REPOSITORY"
echo "Image Tag: $IMAGE_TAG"

# Step 1: Build Docker image
echo "Building Docker image..."
docker build -f docker/Dockerfile -t $ECR_REPOSITORY:$IMAGE_TAG .

# Step 2: Tag image
echo "Tagging image..."
docker tag $ECR_REPOSITORY:$IMAGE_TAG $ECR_REPOSITORY:$IMAGE_TAG

# Step 3: Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPOSITORY

# Step 4: Push image to ECR
echo "Pushing image to ECR..."
docker push $ECR_REPOSITORY:$IMAGE_TAG

# Step 5: Update ECS service
echo "Updating ECS service..."
aws ecs update-service \
    --cluster $ECS_CLUSTER \
    --service $ECS_SERVICE \
    --force-new-deployment \
    --region $AWS_REGION

echo "Deployment initiated. Service is updating..."

# Step 6: Wait for service to stabilize
echo "Waiting for service to stabilize..."
aws ecs wait services-stable \
    --cluster $ECS_CLUSTER \
    --services $ECS_SERVICE \
    --region $AWS_REGION

echo "Deployment completed successfully!"

# Step 7: Check service status
echo "Checking service status..."
aws ecs describe-services \
    --cluster $ECS_CLUSTER \
    --services $ECS_SERVICE \
    --region $AWS_REGION \
    --query 'services[0].[status,runningCount,desiredCount]' \
    --output table


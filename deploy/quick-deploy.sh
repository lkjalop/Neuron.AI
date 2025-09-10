#!/bin/bash
# Quick Multi-Cloud Deployment Script for Neuron-AI
# Usage: ./quick-deploy.sh [aws|azure|gcp|alicloud] [environment]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
CLOUD_PROVIDER=${1:-"aws"}
ENVIRONMENT=${2:-"production"}
PROJECT_NAME="neuron-ai"

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Validate inputs
validate_provider() {
    case $CLOUD_PROVIDER in
        aws|azure|gcp|alicloud)
            log "✅ Valid cloud provider: $CLOUD_PROVIDER"
            ;;
        *)
            error "❌ Invalid cloud provider: $CLOUD_PROVIDER. Use: aws, azure, gcp, or alicloud"
            ;;
    esac
}

validate_environment() {
    case $ENVIRONMENT in
        dev|development|staging|prod|production)
            log "✅ Valid environment: $ENVIRONMENT"
            ;;
        *)
            error "❌ Invalid environment: $ENVIRONMENT. Use: dev, staging, or production"
            ;;
    esac
}

# Check prerequisites
check_prerequisites() {
    log "🔍 Checking prerequisites..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi
    
    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        error "kubectl is not installed. Please install kubectl first."
    fi
    
    # Check if terraform is installed
    if ! command -v terraform &> /dev/null; then
        error "Terraform is not installed. Please install Terraform first."
    fi
    
    # Cloud-specific checks
    case $CLOUD_PROVIDER in
        aws)
            if ! command -v aws &> /dev/null; then
                error "AWS CLI is not installed. Please install AWS CLI first."
            fi
            if [ -z "$AWS_REGION" ]; then
                export AWS_REGION="us-west-2"
                warn "AWS_REGION not set, using default: $AWS_REGION"
            fi
            if [ -z "$AWS_ACCOUNT_ID" ]; then
                error "AWS_ACCOUNT_ID environment variable is required"
            fi
            ;;
        azure)
            if ! command -v az &> /dev/null; then
                error "Azure CLI is not installed. Please install Azure CLI first."
            fi
            ;;
        gcp)
            if ! command -v gcloud &> /dev/null; then
                error "Google Cloud CLI is not installed. Please install gcloud first."
            fi
            if [ -z "$GCP_PROJECT_ID" ]; then
                error "GCP_PROJECT_ID environment variable is required"
            fi
            ;;
        alicloud)
            if ! command -v aliyun &> /dev/null; then
                error "Alibaba Cloud CLI is not installed. Please install aliyun CLI first."
            fi
            ;;
    esac
    
    log "✅ All prerequisites met"
}

# Build and push container image
build_and_push_image() {
    log "🏗️ Building Neuron-AI container image..."
    
    # Create Dockerfile if it doesn't exist
    if [ ! -f "Dockerfile.production" ]; then
        cat > Dockerfile.production << 'EOF'
# Multi-stage build for production
FROM python:3.11-slim as builder

RUN apt-get update && apt-get install -y \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Runtime stage
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 neuron \
    && useradd --uid 10001 --gid neuron --shell /bin/bash --create-home neuron

WORKDIR /app

COPY --from=builder /app/wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache /wheels/*

COPY --chown=neuron:neuron src/ ./src/
COPY --chown=neuron:neuron config/ ./config/

USER 10001

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF
    fi
    
    # Build image
    docker build -f Dockerfile.production -t ${PROJECT_NAME}:${ENVIRONMENT} .
    
    # Push to cloud-specific registry
    case $CLOUD_PROVIDER in
        aws)
            info "Pushing to Amazon ECR..."
            aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
            
            # Create repository if it doesn't exist
            aws ecr describe-repositories --repository-names $PROJECT_NAME --region $AWS_REGION 2>/dev/null || \
                aws ecr create-repository --repository-name $PROJECT_NAME --region $AWS_REGION
            
            docker tag ${PROJECT_NAME}:${ENVIRONMENT} $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${PROJECT_NAME}:${ENVIRONMENT}
            docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${PROJECT_NAME}:${ENVIRONMENT}
            
            export IMAGE_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${PROJECT_NAME}:${ENVIRONMENT}"
            ;;
        azure)
            info "Pushing to Azure Container Registry..."
            if [ -z "$AZURE_REGISTRY" ]; then
                error "AZURE_REGISTRY environment variable is required (e.g., myregistry.azurecr.io)"
            fi
            az acr build --registry $(echo $AZURE_REGISTRY | cut -d'.' -f1) --image ${PROJECT_NAME}:${ENVIRONMENT} .
            export IMAGE_URI="$AZURE_REGISTRY/${PROJECT_NAME}:${ENVIRONMENT}"
            ;;
        gcp)
            info "Pushing to Google Container Registry..."
            gcloud builds submit --tag gcr.io/$GCP_PROJECT_ID/${PROJECT_NAME}:${ENVIRONMENT} .
            export IMAGE_URI="gcr.io/$GCP_PROJECT_ID/${PROJECT_NAME}:${ENVIRONMENT}"
            ;;
        alicloud)
            info "Pushing to Alibaba Container Registry..."
            if [ -z "$ALIBABA_REGISTRY" ]; then
                error "ALIBABA_REGISTRY environment variable is required"
            fi
            # Assuming registry is already configured
            docker tag ${PROJECT_NAME}:${ENVIRONMENT} $ALIBABA_REGISTRY/${PROJECT_NAME}:${ENVIRONMENT}
            docker push $ALIBABA_REGISTRY/${PROJECT_NAME}:${ENVIRONMENT}
            export IMAGE_URI="$ALIBABA_REGISTRY/${PROJECT_NAME}:${ENVIRONMENT}"
            ;;
    esac
    
    log "✅ Container image built and pushed: $IMAGE_URI"
}

# Deploy infrastructure
deploy_infrastructure() {
    log "🚀 Deploying infrastructure to $CLOUD_PROVIDER..."
    
    # Create terraform directory structure
    mkdir -p deploy/terraform/$CLOUD_PROVIDER
    
    # Generate cloud-specific terraform
    case $CLOUD_PROVIDER in
        aws)
            generate_aws_terraform
            ;;
        azure)
            generate_azure_terraform
            ;;
        gcp)
            generate_gcp_terraform
            ;;
        alicloud)
            generate_alicloud_terraform
            ;;
    esac
    
    # Deploy with terraform
    cd deploy/terraform/$CLOUD_PROVIDER
    
    terraform init
    terraform plan -out=tfplan \
        -var="environment=$ENVIRONMENT" \
        -var="image_uri=$IMAGE_URI"
    
    info "Review the terraform plan above. Press Enter to continue or Ctrl+C to cancel..."
    read -r
    
    terraform apply tfplan
    
    # Get cluster credentials
    get_cluster_credentials
    
    cd ../../../
    
    log "✅ Infrastructure deployed successfully"
}

# Generate AWS Terraform configuration
generate_aws_terraform() {
    cat > deploy/terraform/aws/main.tf << 'EOF'
# AWS Infrastructure for Neuron-AI
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Variables
variable "environment" {
  description = "Environment name"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "image_uri" {
  description = "Container image URI"
  type        = string
}

# VPC
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  
  name = "neuron-ai-${var.environment}-vpc"
  cidr = "10.0.0.0/16"
  
  azs             = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  
  enable_nat_gateway = true
  single_nat_gateway = var.environment != "production"
  
  tags = {
    Environment = var.environment
    Project     = "neuron-ai"
  }
}

# EKS
module "eks" {
  source = "terraform-aws-modules/eks/aws"
  
  cluster_name    = "neuron-ai-${var.environment}"
  cluster_version = "1.27"
  
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets
  
  eks_managed_node_groups = {
    main = {
      min_size     = 1
      max_size     = 10
      desired_size = 3
      
      instance_types = ["t3.medium"]
    }
  }
  
  tags = {
    Environment = var.environment
    Project     = "neuron-ai"
  }
}

# RDS
resource "aws_db_instance" "main" {
  identifier = "neuron-ai-${var.environment}"
  
  engine         = "postgres"
  engine_version = "15.3"
  instance_class = var.environment == "production" ? "db.t3.small" : "db.t3.micro"
  
  allocated_storage = 20
  storage_encrypted = true
  
  db_name  = "neuronai"
  username = "neuron"
  password = random_password.db_password.result
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  backup_retention_period = var.environment == "production" ? 7 : 1
  skip_final_snapshot     = true
  
  tags = {
    Environment = var.environment
    Project     = "neuron-ai"
  }
}

resource "random_password" "db_password" {
  length = 16
  special = true
}

resource "aws_db_subnet_group" "main" {
  name       = "neuron-ai-${var.environment}"
  subnet_ids = module.vpc.private_subnets
  
  tags = {
    Environment = var.environment
    Project     = "neuron-ai"
  }
}

resource "aws_security_group" "rds" {
  name_prefix = "neuron-rds-"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
  }
  
  tags = {
    Environment = var.environment
    Project     = "neuron-ai"
  }
}

# ElastiCache
resource "aws_elasticache_subnet_group" "main" {
  name       = "neuron-ai-${var.environment}"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "neuron-ai-${var.environment}"
  description         = "Redis for Neuron-AI"
  
  node_type          = var.environment == "production" ? "cache.t3.small" : "cache.t3.micro"
  port               = 6379
  num_cache_clusters = 1
  
  subnet_group_name = aws_elasticache_subnet_group.main.name
  
  tags = {
    Environment = var.environment
    Project     = "neuron-ai"
  }
}

# Outputs
output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "database_endpoint" {
  value = aws_db_instance.main.endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_replication_group.main.configuration_endpoint_address
}

output "database_password" {
  value     = random_password.db_password.result
  sensitive = true
}
EOF
}

# Generate Azure, GCP, Alibaba Cloud terraform configurations...
generate_azure_terraform() {
    warn "Azure terraform generation not implemented in quick script. Using basic configuration."
}

generate_gcp_terraform() {
    warn "GCP terraform generation not implemented in quick script. Using basic configuration."
}

generate_alicloud_terraform() {
    warn "Alibaba Cloud terraform generation not implemented in quick script. Using basic configuration."
}

# Get cluster credentials
get_cluster_credentials() {
    log "🔧 Configuring kubectl..."
    
    case $CLOUD_PROVIDER in
        aws)
            aws eks update-kubeconfig --region $AWS_REGION --name neuron-ai-$ENVIRONMENT
            ;;
        azure)
            az aks get-credentials --resource-group rg-neuron-ai-$ENVIRONMENT --name aks-neuron-ai-$ENVIRONMENT
            ;;
        gcp)
            gcloud container clusters get-credentials neuron-ai-$ENVIRONMENT --region $GCP_REGION
            ;;
        alicloud)
            warn "Manual kubectl configuration required for Alibaba Cloud"
            ;;
    esac
}

# Deploy application to Kubernetes
deploy_application() {
    log "📦 Deploying Neuron-AI application..."
    
    # Create namespace
    kubectl create namespace neuron-ai-$ENVIRONMENT --dry-run=client -o yaml | kubectl apply -f -
    
    # Get infrastructure outputs
    cd deploy/terraform/$CLOUD_PROVIDER
    DB_ENDPOINT=$(terraform output -raw database_endpoint)
    REDIS_ENDPOINT=$(terraform output -raw redis_endpoint)
    DB_PASSWORD=$(terraform output -raw database_password)
    cd ../../../
    
    # Create Kubernetes manifests
    mkdir -p k8s/$CLOUD_PROVIDER
    
    cat > k8s/$CLOUD_PROVIDER/deployment.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: neuron-ai
  namespace: neuron-ai-$ENVIRONMENT
  labels:
    app: neuron-ai
spec:
  replicas: 3
  selector:
    matchLabels:
      app: neuron-ai
  template:
    metadata:
      labels:
        app: neuron-ai
    spec:
      containers:
      - name: neuron-ai
        image: $IMAGE_URI
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          value: "postgresql://neuron:$DB_PASSWORD@$DB_ENDPOINT:5432/neuronai"
        - name: REDIS_URL
          value: "redis://$REDIS_ENDPOINT:6379/0"
        - name: CLOUD_PROVIDER
          value: "$CLOUD_PROVIDER"
        - name: ENVIRONMENT
          value: "$ENVIRONMENT"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: neuron-ai-service
  namespace: neuron-ai-$ENVIRONMENT
spec:
  selector:
    app: neuron-ai
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
EOF
    
    # Apply manifests
    kubectl apply -f k8s/$CLOUD_PROVIDER/deployment.yaml
    
    # Wait for deployment
    kubectl wait --for=condition=available --timeout=600s deployment/neuron-ai -n neuron-ai-$ENVIRONMENT
    
    log "✅ Application deployed successfully"
}

# Display deployment information
show_deployment_info() {
    log "📊 Deployment Information"
    echo "=========================="
    echo "Cloud Provider: $CLOUD_PROVIDER"
    echo "Environment: $ENVIRONMENT"
    echo "Namespace: neuron-ai-$ENVIRONMENT"
    echo ""
    
    info "Getting service information..."
    kubectl get services -n neuron-ai-$ENVIRONMENT
    
    echo ""
    info "Getting pod status..."
    kubectl get pods -n neuron-ai-$ENVIRONMENT
    
    echo ""
    info "Getting load balancer endpoint..."
    LB_HOST=$(kubectl get service neuron-ai-service -n neuron-ai-$ENVIRONMENT -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "Pending...")
    LB_IP=$(kubectl get service neuron-ai-service -n neuron-ai-$ENVIRONMENT -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
    
    if [ "$LB_HOST" != "Pending..." ] && [ "$LB_HOST" != "" ]; then
        echo "🌐 Access your Neuron-AI deployment at: http://$LB_HOST"
    elif [ "$LB_IP" != "" ]; then
        echo "🌐 Access your Neuron-AI deployment at: http://$LB_IP"
    else
        warn "Load balancer is still provisioning. Check back in a few minutes."
        echo "Monitor with: kubectl get service neuron-ai-service -n neuron-ai-$ENVIRONMENT -w"
    fi
    
    echo ""
    info "Health check: kubectl exec -n neuron-ai-$ENVIRONMENT deployment/neuron-ai -- curl -f http://localhost:8000/healthz"
    echo ""
    info "View logs: kubectl logs -n neuron-ai-$ENVIRONMENT deployment/neuron-ai --follow"
}

# Cleanup function
cleanup() {
    warn "Cleaning up resources..."
    kubectl delete namespace neuron-ai-$ENVIRONMENT --ignore-not-found=true
    
    cd deploy/terraform/$CLOUD_PROVIDER 2>/dev/null && terraform destroy -auto-approve || true
    cd ../../../
}

# Main execution
main() {
    echo ""
    echo "🚀 Neuron-AI Multi-Cloud Quick Deployment"
    echo "=========================================="
    echo ""
    
    validate_provider
    validate_environment
    check_prerequisites
    
    info "Starting deployment to $CLOUD_PROVIDER ($ENVIRONMENT environment)..."
    
    # Trap cleanup on exit
    trap cleanup EXIT
    
    build_and_push_image
    deploy_infrastructure
    deploy_application
    show_deployment_info
    
    # Don't cleanup on successful completion
    trap - EXIT
    
    log "🎉 Deployment completed successfully!"
    echo ""
    echo "Next Steps:"
    echo "1. Test your deployment: curl http://<LOAD_BALANCER_IP>/healthz"
    echo "2. View metrics: http://<LOAD_BALANCER_IP>/metrics"
    echo "3. Scale up: kubectl scale deployment neuron-ai --replicas=5 -n neuron-ai-$ENVIRONMENT"
    echo ""
    echo "To cleanup: kubectl delete namespace neuron-ai-$ENVIRONMENT"
}

# Handle script arguments
case "${1:-help}" in
    help|--help|-h)
        echo "Neuron-AI Multi-Cloud Quick Deployment"
        echo ""
        echo "Usage: $0 [CLOUD_PROVIDER] [ENVIRONMENT]"
        echo ""
        echo "Cloud Providers:"
        echo "  aws      - Amazon Web Services"
        echo "  azure    - Microsoft Azure"
        echo "  gcp      - Google Cloud Platform"
        echo "  alicloud - Alibaba Cloud"
        echo ""
        echo "Environments:"
        echo "  dev, development"
        echo "  staging"
        echo "  prod, production"
        echo ""
        echo "Examples:"
        echo "  $0 aws production"
        echo "  $0 gcp staging"
        echo "  $0 azure dev"
        echo ""
        echo "Required Environment Variables:"
        echo "  AWS: AWS_ACCOUNT_ID, AWS_REGION"
        echo "  Azure: AZURE_REGISTRY"
        echo "  GCP: GCP_PROJECT_ID, GCP_REGION"
        echo "  AliCloud: ALIBABA_REGISTRY"
        ;;
    *)
        main
        ;;
esac
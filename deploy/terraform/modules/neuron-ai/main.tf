# Neuron-AI Universal Terraform Module
# Works across AWS, Azure, GCP, Alibaba Cloud

terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.20"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.10"
    }
  }
}

# Variables
variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "production"
}

variable "cloud_provider" {
  description = "Cloud provider (aws, azure, gcp, alicloud)"
  type        = string
  validation {
    condition     = contains(["aws", "azure", "gcp", "alicloud"], var.cloud_provider)
    error_message = "Cloud provider must be one of: aws, azure, gcp, alicloud."
  }
}

variable "cluster_name" {
  description = "Kubernetes cluster name"
  type        = string
}

variable "replicas" {
  description = "Number of Neuron-AI replicas"
  type        = number
  default     = 3
}

variable "image_repository" {
  description = "Container image repository"
  type        = string
}

variable "image_tag" {
  description = "Container image tag"
  type        = string
  default     = "latest"
}

variable "database_url" {
  description = "Database connection URL"
  type        = string
  sensitive   = true
}

variable "redis_url" {
  description = "Redis connection URL"
  type        = string
  sensitive   = true
}

# Local values for cloud-specific configurations
locals {
  cloud_configs = {
    aws = {
      storage_class = "gp3"
      node_selector = {
        "kubernetes.io/os" = "linux"
      }
      annotations = {
        "service.beta.kubernetes.io/aws-load-balancer-type" = "nlb"
      }
    }
    azure = {
      storage_class = "managed-premium"
      node_selector = {
        "kubernetes.io/os" = "linux"
      }
      annotations = {
        "service.beta.kubernetes.io/azure-load-balancer-internal" = "false"
      }
    }
    gcp = {
      storage_class = "pd-ssd"
      node_selector = {
        "kubernetes.io/os" = "linux"
      }
      annotations = {
        "cloud.google.com/load-balancer-type" = "External"
      }
    }
    alicloud = {
      storage_class = "alicloud-disk-ssd"
      node_selector = {
        "kubernetes.io/os" = "linux"
      }
      annotations = {
        "service.beta.kubernetes.io/alicloud-loadbalancer-spec" = "slb.s2.small"
      }
    }
  }
  
  current_config = local.cloud_configs[var.cloud_provider]
}

# Namespace
resource "kubernetes_namespace" "neuron_ai" {
  metadata {
    name = "neuron-ai-${var.environment}"
    labels = {
      environment = var.environment
      app         = "neuron-ai"
    }
  }
}

# ConfigMap for cloud-specific configuration
resource "kubernetes_config_map" "neuron_config" {
  metadata {
    name      = "neuron-ai-config"
    namespace = kubernetes_namespace.neuron_ai.metadata[0].name
  }

  data = {
    "cloud_provider" = var.cloud_provider
    "environment"    = var.environment
    "log_level"      = var.environment == "production" ? "INFO" : "DEBUG"
  }
}

# Secret for sensitive configuration
resource "kubernetes_secret" "neuron_secrets" {
  metadata {
    name      = "neuron-ai-secrets"
    namespace = kubernetes_namespace.neuron_ai.metadata[0].name
  }

  data = {
    database_url = base64encode(var.database_url)
    redis_url    = base64encode(var.redis_url)
  }
}

# Deployment
resource "kubernetes_deployment" "neuron_ai" {
  metadata {
    name      = "neuron-ai"
    namespace = kubernetes_namespace.neuron_ai.metadata[0].name
    labels = {
      app         = "neuron-ai"
      version     = var.image_tag
      environment = var.environment
    }
  }

  spec {
    replicas = var.replicas

    selector {
      match_labels = {
        app = "neuron-ai"
      }
    }

    template {
      metadata {
        labels = {
          app         = "neuron-ai"
          version     = var.image_tag
          environment = var.environment
        }
      }

      spec {
        node_selector = local.current_config.node_selector

        container {
          name  = "neuron-ai"
          image = "${var.image_repository}:${var.image_tag}"

          port {
            container_port = 8000
            name          = "http"
          }

          env {
            name = "CLOUD_PROVIDER"
            value_from {
              config_map_key_ref {
                name = kubernetes_config_map.neuron_config.metadata[0].name
                key  = "cloud_provider"
              }
            }
          }

          env {
            name = "ENVIRONMENT"
            value_from {
              config_map_key_ref {
                name = kubernetes_config_map.neuron_config.metadata[0].name
                key  = "environment"
              }
            }
          }

          env {
            name = "DATABASE_URL"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.neuron_secrets.metadata[0].name
                key  = "database_url"
              }
            }
          }

          env {
            name = "REDIS_URL"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.neuron_secrets.metadata[0].name
                key  = "redis_url"
              }
            }
          }

          # Cloud-specific environment variables
          dynamic "env" {
            for_each = var.cloud_provider == "aws" ? ["AWS_REGION"] : []
            content {
              name  = "AWS_REGION"
              value = data.aws_region.current[0].name
            }
          }

          resources {
            requests = {
              memory = "512Mi"
              cpu    = "250m"
            }
            limits = {
              memory = "1Gi"
              cpu    = "1000m"
            }
          }

          liveness_probe {
            http_get {
              path = "/healthz"
              port = 8000
            }
            initial_delay_seconds = 30
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 3
          }

          readiness_probe {
            http_get {
              path = "/healthz"
              port = 8000
            }
            initial_delay_seconds = 5
            period_seconds        = 5
            timeout_seconds       = 5
            failure_threshold     = 3
          }
        }
      }
    }
  }
}

# Service
resource "kubernetes_service" "neuron_ai" {
  metadata {
    name        = "neuron-ai-service"
    namespace   = kubernetes_namespace.neuron_ai.metadata[0].name
    annotations = local.current_config.annotations
    labels = {
      app = "neuron-ai"
    }
  }

  spec {
    selector = {
      app = "neuron-ai"
    }

    port {
      name        = "http"
      port        = 80
      target_port = 8000
      protocol    = "TCP"
    }

    type = "LoadBalancer"
  }
}

# Horizontal Pod Autoscaler
resource "kubernetes_horizontal_pod_autoscaler_v2" "neuron_ai" {
  metadata {
    name      = "neuron-ai-hpa"
    namespace = kubernetes_namespace.neuron_ai.metadata[0].name
  }

  spec {
    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = kubernetes_deployment.neuron_ai.metadata[0].name
    }

    min_replicas = var.replicas
    max_replicas = var.replicas * 5

    metric {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type                = "Utilization"
          average_utilization = 70
        }
      }
    }

    metric {
      type = "Resource"
      resource {
        name = "memory"
        target {
          type                = "Utilization"
          average_utilization = 80
        }
      }
    }
  }
}

# ServiceMonitor for Prometheus (if using Prometheus Operator)
resource "kubernetes_manifest" "service_monitor" {
  count = var.environment == "production" ? 1 : 0

  manifest = {
    apiVersion = "monitoring.coreos.com/v1"
    kind       = "ServiceMonitor"
    metadata = {
      name      = "neuron-ai-metrics"
      namespace = kubernetes_namespace.neuron_ai.metadata[0].name
      labels = {
        app = "neuron-ai"
      }
    }
    spec = {
      selector = {
        matchLabels = {
          app = "neuron-ai"
        }
      }
      endpoints = [
        {
          port = "http"
          path = "/metrics"
        }
      ]
    }
  }
}

# Data sources for cloud-specific information
data "aws_region" "current" {
  count = var.cloud_provider == "aws" ? 1 : 0
}

# Outputs
output "namespace" {
  description = "Kubernetes namespace"
  value       = kubernetes_namespace.neuron_ai.metadata[0].name
}

output "service_name" {
  description = "Kubernetes service name"
  value       = kubernetes_service.neuron_ai.metadata[0].name
}

output "deployment_name" {
  description = "Kubernetes deployment name"
  value       = kubernetes_deployment.neuron_ai.metadata[0].name
}

output "load_balancer_ingress" {
  description = "Load balancer ingress information"
  value       = kubernetes_service.neuron_ai.status[0].load_balancer[0].ingress
}
terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  
  # backend "gcs" {
  #   bucket = "sets-terraform-state"
  #   prefix = "tiktok-parser/state"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Variables
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "pubsub.googleapis.com",
    "firestore.googleapis.com",
    "storage.googleapis.com",
    "speech.googleapis.com",
    "vision.googleapis.com",
    "aiplatform.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudkms.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudtrace.googleapis.com",
  ])
  
  project = var.project_id
  service = each.value
  
  disable_dependent_services = false
  disable_on_destroy        = false
}

# KMS Key Ring for CMEK
resource "google_kms_key_ring" "main" {
  name     = "tiktok-parser-keyring"
  location = var.region
  
  depends_on = [google_project_service.apis]
}

# KMS Keys
resource "google_kms_crypto_key" "storage_key" {
  name     = "storage-key"
  key_ring = google_kms_key_ring.main.id
  
  purpose  = "ENCRYPT_DECRYPT"
  
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key" "firestore_key" {
  name     = "firestore-key"
  key_ring = google_kms_key_ring.main.id
  
  purpose = "ENCRYPT_DECRYPT"
  
  lifecycle {
    prevent_destroy = true
  }
}

# Cloud Storage Buckets
resource "google_storage_bucket" "raw_videos" {
  name     = "${var.project_id}-raw-videos"
  location = var.region
  
  uniform_bucket_level_access = true
  
  # encryption {
  #   default_kms_key_name = google_kms_crypto_key.storage_key.id
  # }
  
  lifecycle_rule {
    condition {
      age = 1  # 24 hours
    }
    action {
      type = "Delete"
    }
  }
  
  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket" "keyframes" {
  name     = "${var.project_id}-keyframes"
  location = var.region
  
  uniform_bucket_level_access = true
  
  # encryption {
  #   default_kms_key_name = google_kms_crypto_key.storage_key.id
  # }
  
  lifecycle_rule {
    condition {
      age = 7  # 7 days
    }
    action {
      type = "Delete"
    }
  }
  
  depends_on = [google_project_service.apis]
}

# Terraform state bucket
resource "google_storage_bucket" "terraform_state" {
  name     = "sets-ai-terraform-state"
  location = var.region
  
  versioning {
    enabled = true
  }
  
  uniform_bucket_level_access = true
  
  depends_on = [google_project_service.apis]
}

# Pub/Sub Topic and Subscription  
resource "google_pubsub_topic" "parse_request" {
  name = "parse-request"
  
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_subscription" "worker_subscription" {
  name  = "worker-subscription"
  topic = google_pubsub_topic.parse_request.name
  
  ack_deadline_seconds = 600  # 10 minutes
  
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
  
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }
  
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic" "dead_letter" {
  name = "parse-request-dead-letter"
  
  depends_on = [google_project_service.apis]
}

# Firestore Database
resource "google_firestore_database" "main" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
  
  depends_on = [google_project_service.apis]
}

# Service Accounts
resource "google_service_account" "api_service" {
  account_id   = "tiktok-parser-api"
  display_name = "TikTok Parser API Service Account"
  
  depends_on = [google_project_service.apis]
}

resource "google_service_account" "worker_service" {
  account_id   = "tiktok-parser-worker"
  display_name = "TikTok Parser Worker Service Account"
  
  depends_on = [google_project_service.apis]
}

# IAM Bindings for API Service
resource "google_project_iam_member" "api_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.api_service.email}"
}

resource "google_project_iam_member" "api_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.api_service.email}"
}

resource "google_project_iam_member" "api_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.api_service.email}"
}

resource "google_project_iam_member" "api_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.api_service.email}"
}

# IAM Bindings for Worker Service
resource "google_project_iam_member" "worker_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.worker_service.email}"
}

resource "google_project_iam_member" "worker_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.worker_service.email}"
}

resource "google_project_iam_member" "worker_pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.worker_service.email}"
}

resource "google_project_iam_member" "worker_speech" {
  project = var.project_id
  role    = "roles/speech.client"
  member  = "serviceAccount:${google_service_account.worker_service.email}"
}

resource "google_project_iam_member" "worker_vision" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.worker_service.email}"
}

resource "google_project_iam_member" "worker_aiplatform" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.worker_service.email}"
}

resource "google_project_iam_member" "worker_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.worker_service.email}"
}

resource "google_project_iam_member" "worker_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.worker_service.email}"
}

# Secret Manager Secrets
resource "google_secret_manager_secret" "yt_dlp_cookies" {
  secret_id = "yt-dlp-cookies"
  
  replication {
    auto {}
  }
  
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "tiktok_user_agent" {
  secret_id = "tiktok-user-agent"
  
  replication {
    auto {}
  }
  
  depends_on = [google_project_service.apis]
}

# Cloud Armor Security Policy
resource "google_compute_security_policy" "api_security" {
  name = "tiktok-parser-api-security"
  
  rule {
    action   = "rate_based_ban"
    priority = "1000"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action      = "allow"
      exceed_action       = "deny(429)"
      enforce_on_key      = "IP"
      ban_duration_sec    = 3600
      rate_limit_threshold {
        count        = 30
        interval_sec = 60
      }
    }
  }
  
  rule {
    action   = "allow"
    priority = "2147483647"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }
  
  depends_on = [google_project_service.apis]
}

# Outputs
output "project_id" {
  value = var.project_id
}

output "api_service_account_email" {
  value = google_service_account.api_service.email
}

output "worker_service_account_email" {
  value = google_service_account.worker_service.email
}

output "pubsub_topic" {
  value = google_pubsub_topic.parse_request.name
}

output "pubsub_subscription" {
  value = google_pubsub_subscription.worker_subscription.name
}

output "raw_videos_bucket" {
  value = google_storage_bucket.raw_videos.name
}

output "keyframes_bucket" {
  value = google_storage_bucket.keyframes.name
}
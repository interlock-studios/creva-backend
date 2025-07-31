# TikTok Workout Parser - Makefile
# Standardized commands for development and deployment

# Variables
PROJECT_ID := sets-ai
SERVICE_NAME := tiktok-workout-parser
REGION := us-central1
PYTHON := python3.11
VENV := .venv
PORT := 8080

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

.PHONY: help
help: ## Display this help message
	@echo "$(GREEN)TikTok Workout Parser - Available Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

.PHONY: setup
setup: ## Initial project setup
	@echo "$(GREEN)Setting up project...$(NC)"
	@command -v $(PYTHON) >/dev/null 2>&1 || { echo "$(RED)Python 3.11 is required$(NC)"; exit 1; }
	@$(PYTHON) -m venv $(VENV)
	@echo "$(GREEN)Virtual environment created$(NC)"
	@$(VENV)/bin/pip install --upgrade pip
	@$(VENV)/bin/pip install -r requirements.txt
	@echo "$(GREEN)Dependencies installed$(NC)"
	@cp .env.example .env 2>/dev/null || echo "$(YELLOW)No .env.example found, create .env manually$(NC)"
	@echo "$(GREEN)Setup complete! Activate venv with: source $(VENV)/bin/activate$(NC)"

.PHONY: install
install: ## Install/update dependencies
	@$(VENV)/bin/pip install -r requirements.txt

.PHONY: run
run: ## Run the application locally
	@echo "$(GREEN)Starting application on port $(PORT)...$(NC)"
	@$(VENV)/bin/python main.py

.PHONY: dev
dev: ## Run in development mode with auto-reload
	@echo "$(GREEN)Starting in development mode...$(NC)"
	@ENVIRONMENT=development $(VENV)/bin/uvicorn main:app --reload --host 0.0.0.0 --port $(PORT)

.PHONY: test
test: ## Run tests
	@echo "$(GREEN)Running tests...$(NC)"
	@$(VENV)/bin/pytest tests/ -v --cov=src --cov-report=term-missing

.PHONY: lint
lint: ## Run linting and code quality checks
	@echo "$(GREEN)Running linters...$(NC)"
	@$(VENV)/bin/black src/ main.py --check --line-length=100
	@$(VENV)/bin/flake8 src/ main.py
	@$(VENV)/bin/mypy src/ main.py
	@$(VENV)/bin/bandit -r src/ main.py

.PHONY: format
format: ## Format code with black
	@echo "$(GREEN)Formatting code...$(NC)"
	@$(VENV)/bin/black src/ main.py --line-length=100

.PHONY: security
security: ## Run security checks
	@echo "$(GREEN)Running security checks...$(NC)"
	@$(VENV)/bin/bandit -r src/ main.py
	@$(VENV)/bin/safety check
	@$(VENV)/bin/pip-audit

.PHONY: docker-build
docker-build: ## Build Docker image locally
	@echo "$(GREEN)Building Docker image...$(NC)"
	@docker buildx build --platform linux/amd64 -t $(SERVICE_NAME):local .

.PHONY: docker-run
docker-run: ## Run Docker container locally
	@echo "$(GREEN)Running Docker container...$(NC)"
	@docker run --rm -p $(PORT):$(PORT) \
		-e GOOGLE_CLOUD_PROJECT_ID=$(PROJECT_ID) \
		-e SCRAPECREATORS_API_KEY=$${SCRAPECREATORS_API_KEY} \
		-e ENVIRONMENT=development \
		$(SERVICE_NAME):local

.PHONY: docker-test
docker-test: docker-build ## Build and test Docker image
	@echo "$(GREEN)Testing Docker image...$(NC)"
	@docker run --rm $(SERVICE_NAME):local python -c "import requests; requests.get('http://localhost:8080/health')"

.PHONY: deploy
deploy: ## Deploy to production
	@echo "$(GREEN)Deploying to production...$(NC)"
	@ENVIRONMENT=production ./deploy.sh

.PHONY: deploy-staging
deploy-staging: ## Deploy to staging
	@echo "$(GREEN)Deploying to staging...$(NC)"
	@ENVIRONMENT=staging ./deploy.sh

.PHONY: logs
logs: ## View Cloud Run logs
	@echo "$(GREEN)Fetching logs...$(NC)"
	@gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$(SERVICE_NAME)" --limit=50 --format=json | jq -r '.[] | "\(.timestamp) [\(.severity)] \(.jsonPayload.message // .textPayload)"'

.PHONY: logs-tail
logs-tail: ## Tail Cloud Run logs in real-time
	@echo "$(GREEN)Tailing logs...$(NC)"
	@gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=$(SERVICE_NAME)" --format=json | jq -r '"\(.timestamp) [\(.severity)] \(.jsonPayload.message // .textPayload)"'

.PHONY: create-secrets
create-secrets: ## Create required secrets in Secret Manager
	@echo "$(GREEN)Creating secrets...$(NC)"
	@echo -n "Enter SCRAPECREATORS_API_KEY: " && read -s api_key && echo && \
		echo -n "$$api_key" | gcloud secrets create scrapecreators-api-key --data-file=- || \
		echo "$(YELLOW)Secret already exists$(NC)"

.PHONY: update-secrets
update-secrets: ## Update secrets in Secret Manager
	@echo "$(GREEN)Updating secrets...$(NC)"
	@echo -n "Enter new SCRAPECREATORS_API_KEY: " && read -s api_key && echo && \
		echo -n "$$api_key" | gcloud secrets versions add scrapecreators-api-key --data-file=-

.PHONY: service-info
service-info: ## Display Cloud Run service information
	@echo "$(GREEN)Service Information:$(NC)"
	@gcloud run services describe $(SERVICE_NAME) --region=$(REGION) --format=yaml

.PHONY: test-api
test-api: ## Test the deployed API
	@echo "$(GREEN)Testing deployed API...$(NC)"
	@SERVICE_URL=$$(gcloud run services describe $(SERVICE_NAME) --region=$(REGION) --format='value(status.url)'); \
		echo "Testing $$SERVICE_URL/health"; \
		curl -s "$$SERVICE_URL/health" | jq .

.PHONY: clean
clean: ## Clean up temporary files
	@echo "$(GREEN)Cleaning up...$(NC)"
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@find . -type d -name "*.egg-info" -delete
	@rm -rf .coverage .pytest_cache .mypy_cache
	@echo "$(GREEN)Cleanup complete$(NC)"

.PHONY: setup-gcp
setup-gcp: ## Setup Google Cloud project and services
	@echo "$(GREEN)Setting up Google Cloud project...$(NC)"
	@gcloud config set project $(PROJECT_ID)
	@echo "$(GREEN)Enabling required APIs...$(NC)"
	@gcloud services enable aiplatform.googleapis.com
	@gcloud services enable cloudbuild.googleapis.com
	@gcloud services enable run.googleapis.com
	@gcloud services enable artifactregistry.googleapis.com
	@gcloud services enable secretmanager.googleapis.com
	@gcloud services enable cloudapis.googleapis.com
	@echo "$(GREEN)Creating Artifact Registry repository...$(NC)"
	@gcloud artifacts repositories create $(SERVICE_NAME) \
		--repository-format=docker \
		--location=$(REGION) \
		--description="Docker repository for $(SERVICE_NAME)" || echo "$(YELLOW)Repository already exists$(NC)"
	@echo "$(GREEN)Google Cloud setup complete$(NC)"

.PHONY: validate
validate: lint security test ## Run all validation checks

# Default target
.DEFAULT_GOAL := help
# TikTok Workout Parser V2 - Makefile
# Standardized commands for development and deployment

# Variables
PROJECT_ID := sets-ai
SERVICE_NAME := workout-parser-v2
PRIMARY_REGION := us-central1
SECONDARY_REGIONS := us-east1 europe-west1 asia-southeast1
PYTHON := python3.11
VENV := .venv
PORT := 8080
WORKER_PORT := 8081

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

.PHONY: help
help: ## Display this help message
	@echo "$(GREEN)TikTok Workout Parser V2 - Available Commands$(NC)"
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

.PHONY: check-requirements
check-requirements: ## Check and install requirements if needed
	@echo "$(GREEN)Checking requirements...$(NC)"
	@$(VENV)/bin/pip install -r requirements.txt --quiet

.PHONY: check-port
check-port: ## Check if API port is available
	@echo "$(GREEN)Checking if port $(PORT) is available...$(NC)"
	@lsof -ti:$(PORT) >/dev/null 2>&1 && { echo "$(RED)Port $(PORT) is already in use. Please stop the existing process or use a different port.$(NC)"; exit 1; } || echo "$(GREEN)Port $(PORT) is available$(NC)"

.PHONY: check-ports
check-ports: ## Check if both API and Worker ports are available
	@echo "$(GREEN)Checking if ports $(PORT) and $(WORKER_PORT) are available...$(NC)"
	@lsof -ti:$(PORT) >/dev/null 2>&1 && { echo "$(RED)Port $(PORT) is already in use. Please stop the existing process or use a different port.$(NC)"; exit 1; } || echo "$(GREEN)Port $(PORT) is available$(NC)"
	@lsof -ti:$(WORKER_PORT) >/dev/null 2>&1 && { echo "$(RED)Port $(WORKER_PORT) is already in use. Please stop the existing process or use a different port.$(NC)"; exit 1; } || echo "$(GREEN)Port $(WORKER_PORT) is available$(NC)"

.PHONY: kill-port
kill-port: ## Kill any process using the API port
	@echo "$(YELLOW)Killing any process using port $(PORT)...$(NC)"
	@lsof -ti:$(PORT) | xargs kill -9 2>/dev/null || echo "$(GREEN)No process found on port $(PORT)$(NC)"

.PHONY: kill-ports
kill-ports: ## Kill any process using API or Worker ports
	@echo "$(YELLOW)Killing any process using ports $(PORT) and $(WORKER_PORT)...$(NC)"
	@lsof -ti:$(PORT) | xargs kill -9 2>/dev/null || echo "$(GREEN)No process found on port $(PORT)$(NC)"
	@lsof -ti:$(WORKER_PORT) | xargs kill -9 2>/dev/null || echo "$(GREEN)No process found on port $(WORKER_PORT)$(NC)"

.PHONY: dev
dev: check-requirements check-ports ## Run API and Worker in development mode
	@echo "$(GREEN)Starting API and Worker in development mode...$(NC)"
	@echo "$(YELLOW)API will run on port $(PORT), Worker on port $(WORKER_PORT)$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to stop both services$(NC)"
	@trap 'echo "$(YELLOW)Stopping services...$(NC)"; kill 0' INT; \
	ENVIRONMENT=development $(VENV)/bin/uvicorn main:app --reload --host 0.0.0.0 --port $(PORT) & \
	ENVIRONMENT=development $(VENV)/bin/python -m src.worker.worker_service & \
	wait

.PHONY: dev-force
dev-force: check-requirements kill-ports ## Run API and Worker in development mode (force kill existing process)
	@echo "$(GREEN)Starting API and Worker in development mode...$(NC)"
	@echo "$(YELLOW)API will run on port $(PORT), Worker on port $(WORKER_PORT)$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to stop both services$(NC)"
	@trap 'echo "$(YELLOW)Stopping services...$(NC)"; kill 0' INT; \
	ENVIRONMENT=development $(VENV)/bin/uvicorn main:app --reload --host 0.0.0.0 --port $(PORT) & \
	ENVIRONMENT=development $(VENV)/bin/python -m src.worker.worker_service & \
	wait

.PHONY: dev-api
dev-api: check-requirements check-port ## Run only the API in development mode
	@echo "$(GREEN)Starting API only in development mode...$(NC)"
	@ENVIRONMENT=development $(VENV)/bin/uvicorn main:app --reload --host 0.0.0.0 --port $(PORT)

.PHONY: dev-worker
dev-worker: check-requirements ## Run only the Worker in development mode
	@echo "$(GREEN)Starting Worker only in development mode...$(NC)"
	@ENVIRONMENT=development $(VENV)/bin/python -m src.worker.worker_service

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
deploy: ## Deploy to production (multi-region)
	@echo "$(GREEN)Deploying to production (multi-region)...$(NC)"
	@echo "$(YELLOW)Primary region: $(PRIMARY_REGION)$(NC)"
	@echo "$(YELLOW)Secondary regions: $(SECONDARY_REGIONS)$(NC)"
	@ENVIRONMENT=production PRIMARY_REGION=$(PRIMARY_REGION) SECONDARY_REGIONS=$(SECONDARY_REGIONS) ./deploy.sh

.PHONY: deploy-staging
deploy-staging: ## Deploy to staging
	@echo "$(GREEN)Deploying to staging...$(NC)"
	@ENVIRONMENT=staging PRIMARY_REGION=$(PRIMARY_REGION) ./deploy.sh

.PHONY: deploy-single-region
deploy-single-region: ## Deploy to single region only
	@echo "$(GREEN)Deploying to single region: $(PRIMARY_REGION)...$(NC)"
	@ENVIRONMENT=production SINGLE_REGION=true ./deploy.sh

.PHONY: logs
logs: ## View Cloud Run logs from primary region
	@echo "$(GREEN)Fetching logs from primary region...$(NC)"
	@gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$(SERVICE_NAME) AND resource.labels.location=$(PRIMARY_REGION)" --limit=50 --format=json | jq -r '.[] | "\(.timestamp) [\(.severity)] \(.jsonPayload.message // .textPayload)"'

.PHONY: logs-all-regions
logs-all-regions: ## View Cloud Run logs from all regions
	@echo "$(GREEN)Fetching logs from all regions...$(NC)"
	@gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$(SERVICE_NAME)" --limit=100 --format=json | jq -r '.[] | "\(.timestamp) [\(.severity)] [\(.resource.labels.location)] \(.jsonPayload.message // .textPayload)"'

.PHONY: logs-tail
logs-tail: ## Tail Cloud Run logs in real-time from primary region
	@echo "$(GREEN)Tailing logs from primary region...$(NC)"
	@gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=$(SERVICE_NAME) AND resource.labels.location=$(PRIMARY_REGION)" --format=json | jq -r '"\(.timestamp) [\(.severity)] \(.jsonPayload.message // .textPayload)"'

.PHONY: logs-tail-all
logs-tail-all: ## Tail Cloud Run logs in real-time from all regions
	@echo "$(GREEN)Tailing logs from all regions...$(NC)"
	@gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=$(SERVICE_NAME)" --format=json | jq -r '"\(.timestamp) [\(.severity)] [\(.resource.labels.location)] \(.jsonPayload.message // .textPayload)"'

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
service-info: ## Display Cloud Run service information from primary region
	@echo "$(GREEN)Service Information (Primary Region):$(NC)"
	@gcloud run services describe $(SERVICE_NAME) --region=$(PRIMARY_REGION) --format=yaml

.PHONY: service-info-all
service-info-all: ## Display Cloud Run service information from all regions
	@echo "$(GREEN)Service Information (All Regions):$(NC)"
	@echo "$(YELLOW)Primary Region: $(PRIMARY_REGION)$(NC)"
	@gcloud run services describe $(SERVICE_NAME) --region=$(PRIMARY_REGION) --format="table(metadata.name,status.url,status.conditions[0].type,status.conditions[0].status)" || echo "Not deployed in $(PRIMARY_REGION)"
	@echo "$(YELLOW)Secondary Regions:$(NC)"
	@IFS=',' read -ra REGIONS <<< "$(SECONDARY_REGIONS)"; \
	for region in "$${REGIONS[@]}"; do \
		region=$$(echo $$region | xargs); \
		echo "Region: $$region"; \
		gcloud run services describe $(SERVICE_NAME) --region=$$region --format="table(metadata.name,status.url,status.conditions[0].type,status.conditions[0].status)" 2>/dev/null || echo "Not deployed in $$region"; \
	done

.PHONY: test-api
test-api: ## Test the deployed API in primary region
	@echo "$(GREEN)Testing deployed API in primary region...$(NC)"
	@SERVICE_URL=$$(gcloud run services describe $(SERVICE_NAME) --region=$(PRIMARY_REGION) --format='value(status.url)'); \
		echo "Testing $$SERVICE_URL/health"; \
		curl -s "$$SERVICE_URL/health" | jq .; \
		echo "Testing $$SERVICE_URL/health/regions"; \
		curl -s "$$SERVICE_URL/health/regions" | jq .; \
		echo "Testing $$SERVICE_URL/metrics/performance"; \
		curl -s "$$SERVICE_URL/metrics/performance" | jq .

.PHONY: test-api-all
test-api-all: ## Test the deployed API in all regions
	@echo "$(GREEN)Testing deployed API in all regions...$(NC)"
	@echo "$(YELLOW)Testing Primary Region: $(PRIMARY_REGION)$(NC)"
	@SERVICE_URL=$$(gcloud run services describe $(SERVICE_NAME) --region=$(PRIMARY_REGION) --format='value(status.url)' 2>/dev/null); \
	if [ ! -z "$$SERVICE_URL" ]; then \
		echo "Testing $$SERVICE_URL/health"; \
		curl -s "$$SERVICE_URL/health" | jq . || echo "Health check failed"; \
	else \
		echo "Service not found in $(PRIMARY_REGION)"; \
	fi
	@echo "$(YELLOW)Testing Secondary Regions:$(NC)"
	@IFS=',' read -ra REGIONS <<< "$(SECONDARY_REGIONS)"; \
	for region in "$${REGIONS[@]}"; do \
		region=$$(echo $$region | xargs); \
		echo "Testing region: $$region"; \
		SERVICE_URL=$$(gcloud run services describe $(SERVICE_NAME) --region=$$region --format='value(status.url)' 2>/dev/null); \
		if [ ! -z "$$SERVICE_URL" ]; then \
			echo "Testing $$SERVICE_URL/health"; \
			curl -s "$$SERVICE_URL/health" | jq . || echo "Health check failed for $$region"; \
		else \
			echo "Service not found in $$region"; \
		fi; \
	done

.PHONY: dashboard
dashboard: ## Deploy V2 monitoring dashboard with V1 comparison
	@echo "$(GREEN)Deploying V2 Analytics Dashboard...$(NC)"
	@DASHBOARD_ID=$$(gcloud monitoring dashboards create --config-from-file=monitoring/sets_ai_v2_working_dashboard.json --format="value(name)"); \
		DASHBOARD_SHORT_ID=$$(basename "$$DASHBOARD_ID"); \
		echo "$(GREEN)✅ Dashboard created: $$DASHBOARD_SHORT_ID$(NC)"; \
		echo "$(BLUE)🌐 Dashboard URL: https://console.cloud.google.com/monitoring/dashboards/custom/$$DASHBOARD_SHORT_ID?project=$(PROJECT_ID)$(NC)"

.PHONY: clean
clean: ## Clean up temporary files
	@echo "$(GREEN)Cleaning up...$(NC)"
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@find . -type d -name "*.egg-info" -delete
	@rm -rf .coverage .pytest_cache .mypy_cache
	@echo "$(GREEN)Cleanup complete$(NC)"

.PHONY: setup-gcp
setup-gcp: ## Setup Google Cloud project and services for multi-region deployment
	@echo "$(GREEN)Setting up Google Cloud project for multi-region deployment...$(NC)"
	@gcloud config set project $(PROJECT_ID)
	@echo "$(GREEN)Enabling required APIs...$(NC)"
	@gcloud services enable aiplatform.googleapis.com
	@gcloud services enable cloudbuild.googleapis.com
	@gcloud services enable run.googleapis.com
	@gcloud services enable artifactregistry.googleapis.com
	@gcloud services enable secretmanager.googleapis.com
	@gcloud services enable cloudapis.googleapis.com
	@gcloud services enable firestore.googleapis.com
	@gcloud services enable compute.googleapis.com
	@echo "$(GREEN)Creating Artifact Registry repositories in all regions...$(NC)"
	@echo "Creating repository in primary region: $(PRIMARY_REGION)"
	@gcloud artifacts repositories create $(SERVICE_NAME) \
		--repository-format=docker \
		--location=$(PRIMARY_REGION) \
		--description="Docker repository for $(SERVICE_NAME)" || echo "$(YELLOW)Repository already exists in $(PRIMARY_REGION)$(NC)"
	@echo "Creating repositories in secondary regions..."
	@IFS=',' read -ra REGIONS <<< "$(SECONDARY_REGIONS)"; \
	for region in "$${REGIONS[@]}"; do \
		region=$$(echo $$region | xargs); \
		echo "Creating repository in $$region"; \
		gcloud artifacts repositories create $(SERVICE_NAME) \
			--repository-format=docker \
			--location=$$region \
			--description="Docker repository for $(SERVICE_NAME)" || echo "$(YELLOW)Repository already exists in $$region$(NC)"; \
	done
	@echo "$(GREEN)Google Cloud multi-region setup complete$(NC)"
	@echo "$(YELLOW)Note: You may need to create Firestore indexes for the queue. Run 'make setup-firestore' if you get index errors.$(NC)"

.PHONY: setup-firestore
setup-firestore: ## Setup Firestore database and indexes
	@echo "$(GREEN)Setting up Firestore database...$(NC)"
	@gcloud firestore databases create --location=$(PRIMARY_REGION) --type=firestore-native || echo "$(YELLOW)Firestore database already exists$(NC)"
	@echo "$(GREEN)Deploying Firestore indexes...$(NC)"
	@chmod +x scripts/deploy_indexes.sh
	@./scripts/deploy_indexes.sh
	@echo "$(GREEN)Firestore setup complete$(NC)"

.PHONY: validate
validate: lint security test ## Run all validation checks

.PHONY: benchmark
benchmark: ## Run performance benchmarks against deployed API
	@echo "$(GREEN)Running performance benchmarks...$(NC)"
	@SERVICE_URL=$$(gcloud run services describe $(SERVICE_NAME) --region=$(PRIMARY_REGION) --format='value(status.url)' 2>/dev/null); \
	if [ ! -z "$$SERVICE_URL" ]; then \
		echo "Benchmarking $$SERVICE_URL"; \
		echo "Testing health endpoint..."; \
		time curl -s "$$SERVICE_URL/health" > /dev/null; \
		echo "Testing metrics endpoint..."; \
		time curl -s "$$SERVICE_URL/metrics/performance" > /dev/null; \
		echo "Testing regional health..."; \
		time curl -s "$$SERVICE_URL/health/regions" > /dev/null; \
	else \
		echo "$(RED)Service not deployed. Run 'make deploy' first.$(NC)"; \
	fi

.PHONY: status
status: ## Show deployment status across all regions
	@echo "$(GREEN)Deployment Status:$(NC)"
	@echo "$(YELLOW)Primary Region: $(PRIMARY_REGION)$(NC)"
	@gcloud run services list --filter="metadata.name=$(SERVICE_NAME)" --format="table(metadata.name,status.url,metadata.labels.cloud\.googleapis\.com/location,status.conditions[0].status)" --regions=$(PRIMARY_REGION) || echo "No services found in primary region"
	@echo "$(YELLOW)Secondary Regions: $(SECONDARY_REGIONS)$(NC)"
	@IFS=',' read -ra REGIONS <<< "$(SECONDARY_REGIONS)"; \
	for region in "$${REGIONS[@]}"; do \
		region=$$(echo $$region | xargs); \
		gcloud run services list --filter="metadata.name=$(SERVICE_NAME)" --format="table(metadata.name,status.url,metadata.labels.cloud\.googleapis\.com/location,status.conditions[0].status)" --regions=$$region 2>/dev/null || echo "No services found in $$region"; \
	done

# Default target
.DEFAULT_GOAL := help

# Performance optimization targets
.PHONY: optimize
optimize: ## Run all optimization steps
	@echo "$(GREEN)Running optimization steps...$(NC)"
	@echo "1. Validating code quality..."
	@$(MAKE) validate
	@echo "2. Building optimized Docker image..."
	@$(MAKE) docker-build
	@echo "3. Deploying to production..."
	@$(MAKE) deploy
	@echo "4. Running benchmarks..."
	@sleep 30  # Wait for deployment to stabilize
	@$(MAKE) benchmark
	@echo "$(GREEN)Optimization complete!$(NC)"
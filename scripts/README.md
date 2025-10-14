# Scripts Directory

This directory contains operational scripts for deployment, setup, and maintenance of the Sets AI Backend.

## Directory Structure

```
scripts/
├── deployment/          # Deployment scripts for Cloud Run
├── setup/              # Infrastructure setup scripts
├── firestore_indexes.json
├── deploy_indexes.sh
├── cleanup_indexes.sh
├── performance_test.py
├── test_queue_cleanup.py
└── update_dashboard.sh
```

## Deployment Scripts

Located in `deployment/`

| Script | Purpose | Makefile Command |
|--------|---------|------------------|
| `deploy-parallel.sh` | Multi-region parallel deployment (fast) | `make deploy` |
| `deploy.sh` | Sequential multi-region deployment (reliable) | `make deploy-sequential` |
| `deploy-preview.sh` | Single-region preview deployment | `make deploy-preview` |

**Usage:**
```bash
# Fast parallel deployment to all regions
make deploy

# Slower but more reliable sequential deployment
make deploy-sequential

# Quick preview deployment (single region, App Check disabled)
make deploy-preview
```

## Setup Scripts

Located in `setup/`

### Cloud Armor Security

| Script | Purpose | Makefile Command |
|--------|---------|------------------|
| `setup-cloud-armor-safe.sh` | Setup edge security (bot blocking, DDoS protection) | `make setup-security` |
| `setup-cloud-armor-allowlist.sh` | Strict allowlist policy (deny-all except API endpoints) | `make setup-security-allowlist` |

**Usage:**
```bash
# Setup edge security with bot blocking
make setup-security

# Apply strict allowlist (recommended for production)
make setup-security-allowlist
```

### Load Balancer Configuration

| Script | Purpose | Makefile Command |
|--------|---------|------------------|
| `setup-global-lb-fixed.sh` | Setup global HTTPS load balancer with SSL | `make setup-lb-security` |
| `setup-global-lb-custom-domain.sh` | Setup load balancer with custom domain (api.setsai.app) | `make setup-load-balancer` |
| `update-lb-single-region.sh` | Update LB to route only to us-central1 | `make update-lb-single-region` |
| `add-domain-later.sh` | Add custom domain to existing load balancer | `make add-custom-domain` |

**Usage:**
```bash
# Setup secure global load balancer (multi-region)
make setup-lb-security

# Update to single-region routing (cost optimization)
make update-lb-single-region

# Add custom domain after LB is created
make add-custom-domain
```

**Current Configuration:**
- Load balancer routes **all traffic to us-central1** only
- Secondary regions scale to zero (~95% cost reduction)
- SSL certificate for api.setsai.app
- Cloud Armor security policies active

## Firestore Scripts

| Script | Purpose |
|--------|---------|
| `deploy_indexes.sh` | Deploy Firestore composite indexes |
| `cleanup_indexes.sh` | Remove old/unused Firestore indexes |

**Usage:**
```bash
# Deploy indexes (required for queue queries)
./scripts/deploy_indexes.sh

# Clean up old indexes
./scripts/cleanup_indexes.sh
```

## Testing Scripts

| Script | Purpose |
|--------|---------|
| `performance_test.py` | Performance benchmarking tool |
| `test_queue_cleanup.py` | Test queue cleanup functionality |

**Usage:**
```bash
# Run performance tests
python scripts/performance_test.py

# Test queue cleanup
python scripts/test_queue_cleanup.py
```

## Monitoring Scripts

| Script | Purpose | Makefile Command |
|--------|---------|------------------|
| `update_dashboard.sh` | Update Cloud Monitoring dashboard | `make dashboard-update` |

**Usage:**
```bash
# Update monitoring dashboard
make dashboard-update
```

## Best Practices

1. **Always use Makefile commands** instead of running scripts directly
2. **Test changes** with `make deploy-preview` before production deployment
3. **Monitor logs** after deployment: `make logs` or `make logs-tail`
4. **Check security** regularly: `make test-security`
5. **Verify endpoints** after infrastructure changes: `make test-endpoints`

## Script Maintenance

- All scripts should be idempotent (safe to run multiple times)
- Scripts should include error handling and rollback capabilities
- Always test scripts in preview environment first
- Keep scripts documented in this README

## Quick Reference

```bash
# Full deployment workflow
make deploy                    # Deploy to all regions
make setup-security           # Setup edge security
make update-lb-single-region  # Optimize for single region
make test-endpoints           # Verify everything works
make logs-tail               # Monitor in real-time

# Security checks
make test-security           # Test Cloud Armor rules
make security-logs          # View blocked requests
make blocked-ips            # See recently blocked IPs

# Cost optimization
make update-lb-single-region # Route only to us-central1 (~95% cost reduction)
```

---

**Last Updated:** October 14, 2025  
**Maintained By:** Sets AI Backend Team


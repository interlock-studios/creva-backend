# Complete Deployment Guide

## 🚀 Full Production Deployment with Global Load Balancer

### One-Command Deployment
```bash
# Deploy to all regions (parallel)
make deploy
```

This command deploys API and Worker services to:
- us-central1 (primary) and secondary regions: us-east1, us-west1, europe-west1, europe-west4, europe-north1, asia-southeast1, asia-northeast1, asia-south1, australia-southeast1, southamerica-east1

### Step-by-Step Deployment

If you prefer to deploy in stages:

```bash
# 1. Deploy to all regions first
make deploy

# 2. (Optional) Setup global load balancer with zestai.app
make setup-load-balancer

# 3. Check status
make status-lb
```

### Individual Commands

```bash
# Deploy to single region only
make deploy-single-region

# Deploy to staging environment
make deploy-staging

# Add custom domain to existing load balancer
make add-custom-domain

# Deploy preview (single region, App Check disabled)
make deploy-preview

# Check load balancer and domain status
make status-lb
```

## 🔍 Monitoring and Status

### Check Deployment Status
```bash
# View all regional deployments
make status

# Check load balancer and zestai.app domain
make status-lb

# Test API in all regions
make test-api-all

# View logs from all regions
make logs-all-regions
```

### Expected Output from `make status-lb`
```
Global Load Balancer Status:
Backend Service:
NAME                    BACKENDS                PROTOCOL  LOAD_BALANCING_SCHEME
zest-parser-backend  us-central1,us-east1... HTTPS     EXTERNAL

URL Map:
NAME                   DEFAULT_SERVICE
zest-parser-url-map zest-parser-backend

Global IP: 34.102.136.180

SSL Certificates (zestai.app):
NAME           DOMAINS         MANAGED_STATUS
zestai-ssl-cert api.zestai.app ACTIVE

Domain Status:
Expected domain: api.zestai.app
Load balancer IP: 34.102.136.180
✅ DNS correctly configured
```

## 🌍 Global Architecture After Deployment

```
                    🌐 api.zestai.app
                           |
                    [Global Load Balancer]
                           |
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   [us-central1]     [us-east1]      [europe-west1]
        │                 │                 │
   [Cloud Run]       [Cloud Run]      [Cloud Run]
        │                 │                 │
   [Worker Service]  [Worker Service] [Worker Service]
```

### Traffic Routing:
- **US West Coast** → us-central1
- **US East Coast** → us-east1  
- **Europe/Africa** → europe-west1
- **Asia/Pacific** → asia-southeast1

## 📊 Performance Benefits

### Before (Single Region):
- **Global latency**: 200-500ms from distant regions
- **Single point of failure**: If us-central1 goes down, entire service offline
- **Limited capacity**: Single region scaling limits

### After (Global Load Balancer):
- **Optimized latency**: 50-150ms from any region
- **High availability**: Automatic failover between regions
- **Unlimited scaling**: Each region scales independently
- **Professional domain**: `api.zestai.app` instead of long Google URLs

## 🔧 Troubleshooting

### Common Issues:

**DNS not resolving:**
```bash
# Check DNS propagation
dig api.zestai.app

# Expected: Should return the load balancer IP
# If not, wait up to 24 hours for DNS propagation
```

**SSL certificate not active:**
```bash
# Check certificate status
make status-lb

# Look for MANAGED_STATUS: ACTIVE
# If PROVISIONING, wait 10-60 minutes
```

**Backend services not healthy:**
```bash
# Check individual region health
make test-api-all

# If any region fails, redeploy that region:
make deploy-single-region
```

**Load balancer not routing traffic:**
```bash
# Check backend service configuration
gcloud compute backend-services describe zest-parser-backend --global

# Verify all regions are listed as backends
```

## 💰 Cost Implications

### Load Balancer Costs:
- **Global Load Balancer**: ~$18/month base cost
- **SSL Certificate**: Free (Google-managed)
- **Traffic**: $0.008 per GB processed

### Regional Deployment Costs:
- **Cloud Run**: Pay per request (same as before)
- **Multiple regions**: No additional base cost
- **Firestore**: Single global database (no extra cost)

### Total Additional Cost: ~$20-25/month for global load balancing

## 🎯 Next Steps After Deployment

1. **Update frontend applications** to use `https://api.zestai.app`
2. **Monitor performance** across regions using the monitoring dashboard
3. **Test failover** by temporarily disabling one region
4. **Set up alerts** for load balancer health and SSL certificate expiration
5. **Consider CDN** for static assets if needed

---

**🎉 Your API is now globally distributed with automatic HTTPS and failover!**

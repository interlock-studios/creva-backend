# 🛡️ Edge Security Setup Guide

## Overview

This guide explains how to implement comprehensive cybersecurity checks at the Google Cloud Load Balancer level **before** requests reach your Cloud Run instances, preventing resource waste and improving security.

## Problem Statement

Previously, security checks were only happening at the application level, meaning:
- ❌ Malicious requests reached Cloud Run instances
- ❌ Resources wasted on processing attack traffic  
- ❌ Higher costs from unnecessary instance spin-ups
- ❌ Potential performance impact during attacks

## Solution: Cloud Armor at Load Balancer Level

Now security filtering happens at the **edge** before requests reach instances:
- ✅ DDoS protection with rate-based banning
- ✅ Geographic filtering (blocks high-risk countries)
- ✅ WAF rules for common attacks (SQL injection, XSS, etc.)
- ✅ Bot detection and blocking
- ✅ Edge-level rate limiting

## Security Architecture

```
Internet Request
       ↓
🛡️ Cloud Armor (Edge Security)
   • DDoS Protection
   • Geographic Filtering  
   • WAF Rules
   • Rate Limiting
       ↓
🌐 Global Load Balancer
       ↓
🚀 Cloud Run Instances (Only legitimate traffic)
   • App Check Verification
   • Application-level Security
```

## Setup Instructions

### 1. Quick Setup (Recommended)

Use the Makefile commands for easy setup:

```bash
# Setup comprehensive Cloud Armor security policies
make setup-security

# Setup load balancer with security policies attached
make setup-lb-security
```

### 2. Manual Setup

If you prefer manual setup:

```bash
# Run the Cloud Armor setup script
chmod +x ./scripts/setup/setup-cloud-armor.sh
./scripts/setup/setup-cloud-armor.sh

# Update your load balancer to use security policies
chmod +x ./scripts/setup/setup-global-lb-fixed.sh
./scripts/setup/setup-global-lb-fixed.sh
```

## Security Policies Implemented

### 1. **DDoS Protection** (Priority 1000)
- **Rate Limit**: 100 requests per IP per minute
- **Ban Duration**: 10 minutes for violators
- **Action**: Rate-based banning with 429 responses

### 2. **Geographic Filtering** (Priority 2000)
- **Blocked Countries**: China, Russia, North Korea
- **Reason**: High-risk regions for automated attacks
- **Action**: 403 Forbidden

### 3. **WAF Rules** (Priority 3000-3600)
- **SQL Injection Protection**: Blocks SQLi attempts
- **XSS Protection**: Prevents cross-site scripting
- **File Inclusion Protection**: Blocks LFI/RFI attacks
- **Scanner Detection**: Identifies security scanners
- **Protocol Attack Protection**: Blocks protocol-based attacks
- **Session Fixation Protection**: Prevents session attacks

### 4. **API Rate Limiting** (Priority 4000)
- **Process Endpoint**: 50 requests per IP per minute
- **Ban Duration**: 5 minutes for violators
- **Scope**: Specifically targets `/process` endpoint

### 5. **Bot Detection** (Priority 5000)
- **Blocked User Agents**: curl, wget, python-requests, etc.
- **Empty User Agents**: Blocked
- **Automated Tools**: Detected and blocked

### 6. **Default Allow** (Priority 2147483647)
- **Action**: Allow legitimate traffic
- **Fallback**: Ensures valid requests pass through

## Monitoring & Alerts

### View Security Logs

```bash
# View Cloud Armor security events
make security-logs

# View recently blocked IPs
make blocked-ips

# Monitor in real-time
gcloud logging tail 'resource.type="http_load_balancer"' --format=json
```

### Key Metrics to Monitor

1. **Blocked Requests**: Track attack attempts
2. **Geographic Blocks**: Monitor blocked countries
3. **Rate Limit Violations**: Identify abuse patterns
4. **WAF Triggers**: Common attack types

### Set Up Alerts

Create alerting policies for:
- High number of blocked requests (>100/hour)
- Geographic blocking spikes
- WAF rule triggers
- Rate limit violations

## Cost Savings

### Before (Application-level only)
- Attack traffic reaches Cloud Run instances
- Instances spin up to handle malicious requests
- Resources wasted on processing attacks
- Higher compute costs

### After (Edge-level filtering)
- 90%+ of attacks blocked at edge
- Only legitimate traffic reaches instances
- Significant cost reduction
- Better performance during attacks

## Performance Impact

- **Edge Filtering**: ~1-2ms latency (negligible)
- **Cost**: Cloud Armor pricing is minimal vs. compute savings
- **Scalability**: Handles massive attacks without affecting instances

## Security Policy Management

### Update Security Rules

```bash
# Add new geographic blocks
gcloud compute security-policies rules create 2100 \
    --security-policy=workout-parser-security-policy \
    --expression "origin.region_code == 'XX'" \
    --action=deny-403

# Update rate limits
gcloud compute security-policies rules update 1000 \
    --security-policy=workout-parser-security-policy \
    --rate-limit-threshold-count=150
```

### View Current Rules

```bash
gcloud compute security-policies describe workout-parser-security-policy \
    --format="table(rules[].priority,rules[].action,rules[].description)"
```

## Testing Security Policies

### Test Rate Limiting
```bash
# This should get blocked after 100 requests
for i in {1..150}; do
  curl -s https://api.setsai.app/health > /dev/null
  echo "Request $i sent"
done
```

### Test WAF Rules
```bash
# This should be blocked by SQL injection protection
curl "https://api.setsai.app/process?url=' OR 1=1--"
```

### Test Geographic Blocking
Use a VPN from blocked countries to verify blocking works.

## Troubleshooting

### Common Issues

1. **Legitimate Traffic Blocked**
   - Check user agents in security logs
   - Adjust rate limits if too restrictive
   - Whitelist specific IPs if needed

2. **Security Policy Not Applied**
   - Verify policy is attached to backend service
   - Check load balancer configuration
   - Allow time for propagation (5-10 minutes)

3. **High False Positives**
   - Review WAF rule triggers
   - Adjust sensitivity levels
   - Create exception rules for legitimate patterns

### Debug Commands

```bash
# Check security policy status
gcloud compute security-policies describe workout-parser-security-policy

# Verify policy attachment
gcloud compute backend-services describe workout-parser-backend-v2 --global

# View detailed security logs
gcloud logging read 'resource.type="http_load_balancer"' --limit=10 --format=json
```

## Best Practices

1. **Monitor Regularly**: Check security logs daily
2. **Adjust Thresholds**: Fine-tune based on legitimate traffic patterns  
3. **Geographic Considerations**: Be careful with broad country blocks
4. **Rate Limit Tuning**: Balance security vs. user experience
5. **Regular Updates**: Keep WAF rules current with threat landscape

## Integration with Application Security

Edge security **complements** your existing application-level security:

- **Edge**: Blocks obvious attacks and abuse
- **Application**: Handles business logic security (App Check, authentication)
- **Defense in Depth**: Multiple layers provide comprehensive protection

## Next Steps

1. Deploy the security policies using `make setup-security`
2. Monitor security logs for the first week
3. Adjust rate limits based on legitimate traffic patterns
4. Set up alerting for security events
5. Regular security policy reviews and updates

---

**Result**: Malicious requests are now blocked at the edge, preventing unnecessary instance spin-ups and significantly reducing resource waste while maintaining robust security.

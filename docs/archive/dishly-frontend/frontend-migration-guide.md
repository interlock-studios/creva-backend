# Frontend Migration Guide: US-Central1 → Global Load Balancer

## 🎯 Migration Overview

**From:** `https://zest-parser-g4zcestszq-uc.a.run.app`  
**To:** `https://api.zestai.app`

## �� Code Changes Required

### 1. Environment Variables / Config

**Before:**
```javascript
// .env or config file
REACT_APP_API_URL=https://zest-parser-g4zcestszq-uc.a.run.app
```

**After:**
```javascript
// .env or config file  
REACT_APP_API_URL=https://api.zestai.app
```

### 2. API Client Configuration

**Before:**
```javascript
// api.js or similar
const API_BASE_URL = 'https://zest-parser-g4zcestszq-uc.a.run.app';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});
```

**After:**
```javascript
// api.js or similar
const API_BASE_URL = 'https://api.zestai.app';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // Keep same timeout
});
```

### 3. Direct API Calls

**Before:**
```javascript
// Direct fetch calls
const response = await fetch('https://zest-parser-g4zcestszq-uc.a.run.app/process', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ url: tiktokUrl })
});
```

**After:**
```javascript
// Direct fetch calls
const response = await fetch('https://api.zestai.app/process', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ url: tiktokUrl })
});
```

### 4. WebSocket Connections (if any)

**Before:**
```javascript
const ws = new WebSocket('wss://zest-parser-g4zcestszq-uc.a.run.app/ws');
```

**After:**
```javascript
const ws = new WebSocket('wss://api.zestai.app/ws');
```

## 🚀 Benefits After Migration

### Performance Improvements:
- **Global Users:** Automatically routed to nearest region
- **US East Coast:** ~50ms faster (us-east1 vs us-central1)
- **Europe:** ~200ms faster (europe-west1 vs us-central1)  
- **Asia:** ~300ms faster (asia-southeast1 vs us-central1)

### Reliability Improvements:
- **Automatic Failover:** If one region fails, traffic routes to others
- **Load Distribution:** Traffic spread across 4 regions
- **SSL/HTTPS:** Automatic certificate management

### Professional Benefits:
- **Custom Domain:** `api.zestai.app` instead of long Google URL
- **Branding:** Consistent with your domain
- **Future-Proof:** Easy to add more regions or features

## ⚠️ Migration Checklist

### Pre-Migration:
- [ ] DNS record added and propagated
- [ ] SSL certificate provisioned (check: `curl -I https://api.zestai.app`)
- [ ] Load balancer health check passing

### During Migration:
- [ ] Update environment variables
- [ ] Update API client configuration  
- [ ] Update any hardcoded URLs
- [ ] Update documentation/README
- [ ] Test all API endpoints

### Post-Migration:
- [ ] Monitor error rates
- [ ] Check performance metrics
- [ ] Verify global routing works
- [ ] Update any external integrations

## 🧪 Testing Commands

```bash
# Test health endpoint
curl -s https://api.zestai.app/health | jq .

# Test process endpoint
curl -X POST https://api.zestai.app/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@example/video/123"}' | jq .

# Test from different locations
# (Use VPN or ask users in different regions to test)
```

## 🔄 Rollback Plan (if needed)

If issues arise, you can quickly rollback:

```javascript
// Emergency rollback - change back to:
const API_BASE_URL = 'https://zest-parser-g4zcestszq-uc.a.run.app';
```

The regional endpoints remain active, so rollback is instant.

## 📊 Monitoring

After migration, monitor:
- **Response times** from different regions
- **Error rates** across all endpoints  
- **SSL certificate** auto-renewal
- **DNS resolution** globally

## 🎉 You're Done!

Once DNS propagates (up to 24 hours), your users will automatically get:
- ✅ Faster responses (routed to nearest region)
- ✅ Better reliability (multi-region failover)  
- ✅ Professional API endpoint
- ✅ Automatic HTTPS with your domain

# Firebase App Check Monitoring Guide

## 🎯 **Dashboard Overview**

Your Firebase App Check monitoring dashboard is now live! This guide shows you how to monitor verified vs unverified requests and make data-driven decisions about when to enable strict mode.

### 📊 **Dashboard URL**
```
https://console.cloud.google.com/monitoring/dashboards/custom/8ae097d9-423a-49e0-8e4d-e4286b46da96?project=sets-ai
```

## 📈 **What You Can Monitor**

### **Real-Time Metrics**
- ✅ **Verified Requests**: Requests with valid App Check tokens
- ❌ **Unverified Requests**: Requests without App Check tokens  
- 🚫 **Invalid Tokens**: Requests with invalid/expired App Check tokens
- 📊 **Total Request Volume**: Overall API usage

### **Performance Metrics**
- 🕐 **API Response Times**: 95th percentile latency
- 📈 **Request Rate**: Requests per minute
- ❌ **Error Rates**: 4xx and 5xx errors
- 🖥️ **Instance Count**: Active Cloud Run instances

## 🔍 **How to Use the Dashboard**

### **1. Check Current Status**
```bash
# Get live metrics from your API
curl -s "https://workout-parser-341666880405.us-central1.run.app/status" | jq '.app_check'
```

**Example Response:**
```json
{
  "required": false,
  "stats": {
    "initialized": true,
    "cached_tokens": 0,
    "cache_ttl_minutes": 5.0
  },
  "metrics": {
    "verified_requests": 0,
    "unverified_requests": 5,
    "invalid_tokens": 0,
    "total_requests": 5
  }
}
```

### **2. Monitor Verification Rate**
Calculate your App Check adoption rate:
```
Verification Rate = verified_requests / total_requests * 100%
```

### **3. Decision Making Matrix**

| **Verification Rate** | **Action** | **Reason** |
|----------------------|------------|------------|
| **< 10%** | Keep optional mode | Too few clients support App Check |
| **10% - 50%** | Monitor & educate users | Gradual adoption in progress |
| **50% - 80%** | Plan enforcement timeline | Good adoption, prepare for strict mode |
| **> 80%** | ✅ **Enable strict mode** | Most clients support App Check |

## 🚀 **Enabling Strict Mode**

When you're ready to require App Check tokens for all requests:

### **Step 1: Set Environment Variable**
```bash
# In your deployment configuration
export APPCHECK_REQUIRED=true
```

### **Step 2: Deploy**
```bash
make deploy
```

### **Step 3: Verify**
```bash
# Check that App Check is now required
curl -s "https://workout-parser-341666880405.us-central1.run.app/status" | jq '.app_check.required'
# Should return: true
```

### **Step 4: Test Enforcement**
```bash
# This should now return 401 Unauthorized
curl -X POST "https://workout-parser-341666880405.us-central1.run.app/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@test/video/123"}'
```

## 📊 **Log-Based Metrics**

Three custom metrics have been created for detailed monitoring:

### **1. Verified Requests**
- **Metric**: `logging.googleapis.com/user/appcheck_verified_requests`
- **Description**: Tracks requests with valid App Check tokens
- **Filter**: `jsonPayload.metric="verified"`

### **2. Unverified Requests**  
- **Metric**: `logging.googleapis.com/user/appcheck_unverified_requests`
- **Description**: Tracks requests without App Check tokens
- **Filter**: `jsonPayload.metric="unverified"`

### **3. Invalid Tokens**
- **Metric**: `logging.googleapis.com/user/appcheck_invalid_tokens`
- **Description**: Tracks requests with invalid App Check tokens
- **Filter**: `jsonPayload.metric="invalid"`

## 🔔 **Setting Up Alerts**

### **High Unverified Request Rate Alert**
Get notified when >80% of requests are unverified:

1. Go to [Alerting Policies](https://console.cloud.google.com/monitoring/alerting/policies?project=sets-ai)
2. Click **Create Policy**
3. Set condition:
   - **Metric**: `logging.googleapis.com/user/appcheck_unverified_requests`
   - **Threshold**: > 80% of total requests
   - **Duration**: 5 minutes

### **App Check Service Health Alert**
Get notified if App Check service becomes unhealthy:

1. **Metric**: Look for `jsonPayload.services.app_check="unhealthy"` in logs
2. **Threshold**: > 0 occurrences
3. **Duration**: 1 minute

### **Error Rate Spike Alert**
Monitor for increased 401 errors when strict mode is enabled:

1. **Metric**: `run.googleapis.com/request_count`
2. **Filter**: `response_code_class="4xx"`
3. **Threshold**: > 50% increase from baseline

## 📱 **Client-Side Implementation Status**

Track which clients support App Check by monitoring the `app_id` field in verified requests:

### **View App IDs in Logs**
```bash
# Check which apps are sending verified requests
gcloud logging read 'resource.type="cloud_run_revision" 
AND jsonPayload.event_type="appcheck_metric" 
AND jsonPayload.metric="verified"' \
--limit=50 --format='value(jsonPayload.app_id)'
```

### **App Check Setup Status**
| **Platform** | **Status** | **App ID** |
|--------------|------------|------------|
| iOS | ⏳ Configure | `sets-ai-ios` |
| Android | ⏳ Configure | `sets-ai-android` |
| Web | ⏳ Configure | `sets-ai-web` |

## 🎯 **Recommended Monitoring Schedule**

### **Daily** (During Rollout)
- Check verification rate trend
- Monitor error rates
- Review top app IDs

### **Weekly**
- Analyze adoption patterns
- Update client teams on progress
- Plan next phase if needed

### **Monthly**
- Review alert configurations
- Optimize thresholds based on data
- Document lessons learned

## 🛠️ **Troubleshooting**

### **Low Verification Rate**
1. **Check client configurations** - Ensure apps are sending tokens
2. **Review Firebase Console** - Verify App Check is enabled
3. **Test token generation** - Use Firebase SDK debugging
4. **Check network issues** - Verify connectivity to Firebase

### **High Invalid Token Rate**
1. **Clock synchronization** - Ensure client device times are correct
2. **Token refresh** - Implement proper token refresh logic
3. **App registration** - Verify app IDs match Firebase project
4. **Provider configuration** - Check DeviceCheck/Play Integrity setup

### **Dashboard Not Showing Data**
1. **Wait 2-5 minutes** - Metrics have slight delay
2. **Check log ingestion** - Verify logs are reaching Cloud Logging
3. **Validate filters** - Ensure log-based metric filters are correct
4. **Test API endpoints** - Generate some traffic to create data

## 📚 **Additional Resources**

- **Firebase App Check Docs**: https://firebase.google.com/docs/app-check
- **Cloud Monitoring**: https://console.cloud.google.com/monitoring?project=sets-ai
- **Cloud Logging**: https://console.cloud.google.com/logs/query?project=sets-ai
- **Your API Health**: https://workout-parser-341666880405.us-central1.run.app/health

## 🎉 **Success Criteria**

You're ready to enable strict mode when:
- ✅ **>80% verification rate** for 7+ days
- ✅ **Low invalid token rate** (<5%)
- ✅ **All critical clients** support App Check
- ✅ **Error monitoring** is configured
- ✅ **Rollback plan** is documented

---

**Happy Monitoring! 📊✨**

Your Firebase App Check implementation is now production-ready with comprehensive monitoring. Use this dashboard to make data-driven decisions about when to enable strict enforcement.

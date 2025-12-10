#!/bin/bash

# Script to add custom domain to existing load balancer
# Usage: ./add-domain-later.sh your-domain.com

DOMAIN=$1
PROJECT_ID="creva-e6435"

if [ -z "$DOMAIN" ]; then
    echo "Usage: ./add-domain-later.sh your-domain.com"
    exit 1
fi

echo "🌐 Adding domain $DOMAIN to existing load balancer..."

# Get current global IP
GLOBAL_IP=$(gcloud compute forwarding-rules describe creva-parser-forwarding-rule --global --format="value(IPAddress)" --project=$PROJECT_ID)

echo "📋 Steps to complete:"
echo "1. Point your domain's A record to: $GLOBAL_IP"
echo "2. Wait for DNS propagation (5-60 minutes)"
echo "3. Run this script again to set up SSL"

# Check if domain is pointing to our IP
echo "🔍 Checking DNS..."
RESOLVED_IP=$(dig +short $DOMAIN | tail -n1)

if [ "$RESOLVED_IP" = "$GLOBAL_IP" ]; then
    echo "✅ DNS is configured correctly!"
    
    # Create SSL certificate
    echo "🔒 Creating SSL certificate..."
    gcloud compute ssl-certificates create creva-parser-ssl-cert \
        --domains=$DOMAIN \
        --global \
        --project=$PROJECT_ID
    
    # Create HTTPS target proxy
    echo "🎯 Creating HTTPS proxy..."
    gcloud compute target-https-proxies create creva-parser-https-proxy \
        --url-map=creva-parser-url-map \
        --ssl-certificates=creva-parser-ssl-cert \
        --global \
        --project=$PROJECT_ID
    
    # Create HTTPS forwarding rule
    echo "🌐 Creating HTTPS forwarding rule..."
    gcloud compute forwarding-rules create creva-parser-https-rule \
        --global \
        --target-https-proxy=creva-parser-https-proxy \
        --ports=443 \
        --project=$PROJECT_ID
    
    echo "✅ Domain setup complete!"
    echo "🎉 Your API is now available at: https://$DOMAIN"
    echo "⏰ SSL certificate may take 10-60 minutes to provision"
    
else
    echo "❌ Domain not pointing to load balancer yet"
    echo "Current DNS: $RESOLVED_IP"
    echo "Expected: $GLOBAL_IP"
    echo "Please update your DNS and try again"
fi


# Setup Scripts

Infrastructure setup and configuration scripts for Google Cloud Platform.

## Active Scripts

### Cloud Armor Security
- **`setup-cloud-armor-safe.sh`** - Bot blocking, DDoS protection, WAF rules
- **`setup-cloud-armor-allowlist.sh`** - Strict allowlist (deny-all except valid endpoints)

### Load Balancer
- **`setup-global-lb-fixed.sh`** - Global HTTPS load balancer with SSL and security
- **`setup-global-lb-custom-domain.sh`** - Load balancer with api.setsai.app domain
- **`update-lb-single-region.sh`** - Update to single-region routing (cost optimization)
- **`add-domain-later.sh`** - Add custom domain to existing load balancer

## Usage

Always use Makefile commands:

```bash
make setup-security              # Cloud Armor security
make setup-lb-security          # Global load balancer
make update-lb-single-region    # Single region optimization
```

See parent directory README for full documentation.


# Monitoring & Dashboards

## 📊 Current Dashboards

### Production Dashboard
- **File**: `dashboards/production_dashboard.json`
- **Purpose**: Main monitoring dashboard for production API
- **Metrics**: Performance, errors, security, GenAI usage

## 📁 Directory Structure

```
monitoring/
├── README.md                           # This file
├── DASHBOARD_GUIDE.md                  # Detailed dashboard guide
├── dashboards/
│   └── production_dashboard.json      # Main production dashboard
└── archive/                           # Old/deprecated dashboards
    ├── comprehensive_appcheck_dashboard.json
    ├── comprehensive_security_dashboard.json
    ├── enhanced_dashboard.json
    ├── final_dashboard.json
    ├── security_dashboard.json
    ├── sets_ai_analytics_dashboard.json
    ├── ultimate_sets_ai_dashboard.json
    └── working_security_dashboard.json
```

## 🚀 Quick Start

1. **Deploy Dashboard**: Use the production dashboard for monitoring
2. **View Metrics**: Access Google Cloud Monitoring console
3. **Archive Old**: Keep old dashboards in `archive/` for reference

## 🧹 Maintenance

- Keep only active dashboards in `dashboards/`
- Archive deprecated dashboards in `archive/`
- Update this README when adding new dashboards

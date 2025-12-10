# Documentation Index

This directory contains organized documentation for the Creva Backend project.

## 📁 Directory Structure

### `/architecture/`
Technical architecture and design documents:
- *(Documents will be added as Creva architecture is defined)*

### `/operations/`
Operational guides and optimizations:
- `PERFORMANCE_OPTIMIZATIONS.md` - Performance tuning and optimization strategies
- `SECURITY_ENHANCEMENTS.md` - Security improvements and best practices
- `DEPLOYMENT_GUIDE.md` - Full production deployment guide
- `EDGE_SECURITY_SETUP.md` - Cloud Armor policies

### `/archive/`
Historical documents from previous versions:
- `dishly-prds/` - Archived PRDs from Dishly backend
- `dishly-frontend/` - Archived frontend docs

### Root Documentation Files
- `CLAUDE.md` - AI assistant context for Creva backend
- `../PROJECT_STRUCTURE.md` - Quick development guide (in project root)
- `../README.md` - Main project README (in project root)

## 🔗 Quick Links

- **API (prod)**: `https://creva-parser-{hash}.run.app`
- **Preview**: `make deploy-preview`

## 📦 Infrastructure

- **GCP Project**: `creva-e6435`
- **Firebase Project**: `creva-e6435`
- **Services**: `creva-parser`, `creva-parser-worker`
- **Service Account**: `creva-parser@creva-e6435.iam.gserviceaccount.com`

## 🎯 Key Features

- **Transcript Extraction**: Full text from TikTok/Instagram videos
- **Hook Detection**: Identify attention-grabbing openers
- **Long-Term Caching**: 365+ day cache for instant results
- **Multi-Platform**: TikTok and Instagram support

## 📖 Getting Started

- **Getting Started**: See `../README.md` in the project root
- **Development Guide**: See `../PROJECT_STRUCTURE.md` in the project root
- **Architecture Details**: See `CLAUDE.md` in this directory

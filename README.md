# WeedFinder.ai POC

AI-powered cannabis product search and recommendation platform. This POC demonstrates the core functionality with a single dispensary using POSaBIT POS integration.

## Features

- 🔍 **Natural Language Search**: Users can search using phrases like "something for relaxation that won't make me sleepy"
- 🤖 **AI-Powered Recommendations**: GPT-3.5 analyzes products and provides intelligent suggestions
- 📊 **ROI Tracking**: Automated basket-lift calculation and weekly impact reports
- 🌿 **Strain Classification**: Automatic strain effect and attribute classification
- 💾 **Multi-POS Support**: Extensible adapter pattern (POSaBIT implemented)
- ⚡ **Fast Performance**: Redis caching and optimized queries (<1s response time)

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL with pgvector extension
- Redis (optional, for caching)
- OpenAI API key

### 1. Environment Setup

```bash
# Clone and setup
git clone <repository>
cd weedfinder

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/weedfinder

# OpenAI
OPENAI_API_KEY=sk-your-openai-api-key-here

# POSaBIT Store Credentials (from your conversation)
POSABIT_FEED_ID=
POSABIT_MERCHANT_TOKEN=
POSABIT_API_TOKEN=

# Redis (optional)
REDIS_URL=redis://localhost:6379
```

### 3. Database Setup

```bash
# Initialize database schema
python init_db.py
```

### 4. Data Ingestion

```bash
# Fetch and classify products from POSaBIT
python ingest.py
```

### 5. Start the API

```bash
# Start the FastAPI server
python app.py
```

The API will be available at `http://localhost:8000`

### 6. Test the Widget

Open `widget/index.html` in your browser to test the search functionality.

## API Endpoints

### Search Products
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "something for relaxation", 
    "store_id": "pend-oreille-cannabis-co",
    "limit": 3
  }'
```

### Get Store Products
```bash
curl http://localhost:8000/stores/pend-oreille-cannabis-co/products
```

### Get ROI Metrics
```bash
curl http://localhost:8000/stores/pend-oreille-cannabis-co/roi
```

### Health Check
```bash
curl http://localhost:8000/health
```

## Project Structure

```
weedfinder/
├── app.py                 # FastAPI application
├── requirements.txt       # Python dependencies
├── init_db.py            # Database initialization
├── ingest.py             # Data ingestion script
├── Dockerfile            # Container configuration
├── src/                  # Core modules
│   ├── database.py       # Database operations
│   ├── posabit_adapter.py # POSaBIT integration
│   ├── search_service.py # AI search logic
│   ├── roi_tracker.py    # ROI calculation
│   └── strain_classifier.py # Strain classification
├── widget/               # Frontend widget
│   └── index.html        # Demo widget
└── weedfinder/plan/      # Business and technical plans
```

## Core Components

### 1. Database Schema
- **stores**: Dispensary information and POS configuration
- **strains**: Canonical strain data with AI-classified effects
- **products**: Store inventory with normalized attributes
- **search_logs**: Query analytics for optimization
- **sales_baseline/current**: ROI tracking data

### 2. Search Pipeline
1. **Intent Extraction**: GPT-3.5 processes natural language queries
2. **Product Matching**: Pass-through approach for POC (vector search ready)
3. **Result Ranking**: AI-powered relevance scoring with explanations
4. **Caching**: Redis-based caching for performance

### 3. ROI Tracking
- Automated baseline calculation from POS exports
- Real-time basket-lift monitoring
- Weekly impact email reports
- Configurable A/B testing periods

## Testing

### Test POSaBIT Connection
```bash
python -m src.posabit_adapter
```

### Test Search Service
```bash
python -m src.search_service
```

### Test Strain Classification
```bash
python -m src.strain_classifier
```

## Deployment

### Docker
```bash
# Build image
docker build -t weedfinder-api .

# Run container
docker run -p 8000:8000 --env-file .env weedfinder-api
```

### Fly.io (Recommended for POC)
```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Launch app
fly launch --name weedfinder-poc

# Set secrets
fly secrets set OPENAI_API_KEY=sk-xxx POSABIT_API_TOKEN=xxx

# Deploy
fly deploy
```

## Next Steps (MVP Development)

1. **Vector Search**: Implement pgvector for better search quality
2. **Multi-Store**: Add support for additional dispensaries
3. **Widget Embedding**: Create embeddable JavaScript widget
4. **Advanced Analytics**: Expand ROI tracking and insights
5. **Strain Enhancement**: Add terpene profiles and lab data

## Cost Estimates (POC)

- **OpenAI API**: ~$15-30/month (500-1000 queries/day)
- **Infrastructure**: ~$25/month (Fly.io + Postgres)
- **Total**: ~$40-55/month

## Support

For questions or issues:
- Check the logs: `tail -f app.log`
- Test individual components using the test functions
- Verify environment variables are set correctly

## License

Proprietary - WeedFinder.ai POC
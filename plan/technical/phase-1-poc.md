# Phase 1: POC Implementation (Weeks 0-4)
*Single Store, Minimal Viable Product*

## Objectives

**Primary Goal**: Prove the core value proposition with one local dispensary
- Deploy a working AI search widget on their website
- Demonstrate measurable basket lift within 14 days
- Establish technical foundation for multi-store scaling
- Generate first $49 in monthly recurring revenue

**Success Metrics**:
- Widget responds to queries in < 1 second (p95)
- Store owner reports positive feedback from customers
- Automated basket-lift email shows > 5% AOV increase
- Technical stack can handle 100+ queries/day without issues

## Week-by-Week Implementation Plan

### Week 0: Foundation Setup (Weekend Project)

**Day 1-2: Local Development Environment**
```bash
# Project initialization
mkdir weedfinder && cd weedfinder
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn psycopg2-binary pgvector openai python-dotenv

# Basic FastAPI app
echo 'from fastapi import FastAPI
app = FastAPI()

@app.get("/ping")
async def pong():
    return {"pong": "🫡"}

@app.post("/search")
async def search(query: dict):
    # TODO: Implement search logic
    return {"results": []}' > app.py

# Test locally
uvicorn app:app --reload
```

**Day 3-4: POSaBIT Integration**
```python
# fetch_posabit.py
import requests
import json
from datetime import datetime

def fetch_posabit_feed(feed_id: str, merchant_token: str, api_token: str):
    url = f"https://app.posabit.com/mcx/pend-oreille-cannabis-co/venue/newport/v1/menu_feeds/{feed_id}/product_data"
    
    headers = {
        "Authorization": f"Bearer {api_token}",
        "merchantToken": merchant_token,
        "Accept": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to fetch feed: {response.status_code}")

# Test with actual store credentials
if __name__ == "__main__":
    data = fetch_posabit_feed(
        feed_id="375112db85ccaea4",
        merchant_token="gO-sys8K_GRwlCylbRc7vA", 
        api_token="1vm1ax-tIxpocYteXD1FWA"
    )
    print(f"Fetched {len(data.get('product_data', {}).get('menu_items', []))} products")
```

**Day 5-7: Pass-Through GPT Search**
```python
# search.py
import openai
import json
from typing import List, Dict

def search_products(user_query: str, products: List[Dict]) -> List[Dict]:
    # Format products for GPT context
    product_context = []
    for p in products[:200]:  # Limit context size
        context_item = f"{p['product_name']} | {p.get('strain', '')} | {p.get('potency_thc', 0)}% THC | {p.get('category', '')}"
        product_context.append(context_item)
    
    prompt = f"""You are WeedFinder.ai, a cannabis product recommendation assistant.
    
User Query: {user_query}

Available Products:
{chr(10).join(product_context)}

Return the top 3 most relevant products as JSON with this format:
{{"results": [{{"name": "product name", "reason": "why this matches", "thc": "X%", "price": "$Y"}}]}}"""

    response = openai.chat.completions.create(
        model="gpt-3.5-turbo-0125",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)
```

### Week 1: Widget Development

**Frontend Widget (Next.js/React)**
```javascript
// widget/src/WeedFinderWidget.jsx
import { useState } from 'react'

export default function WeedFinderWidget({ apiUrl, storeId }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)

  const handleSearch = async () => {
    if (!query.trim()) return
    
    setLoading(true)
    try {
      const response = await fetch(`${apiUrl}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, store_id: storeId })
      })
      
      const data = await response.json()
      setResults(data.results || [])
    } catch (error) {
      console.error('Search failed:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="weedfinder-widget">
      <div className="search-box">
        <input
          type="text"
          placeholder="Describe what you're looking for..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
        />
        <button onClick={handleSearch} disabled={loading}>
          {loading ? 'Searching...' : 'Find Products'}
        </button>
      </div>
      
      <div className="results">
        {results.map((product, idx) => (
          <div key={idx} className="product-card">
            <h4>{product.name}</h4>
            <p>{product.reason}</p>
            <div className="details">
              <span>{product.thc}</span>
              <span>{product.price}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

**Embeddable Script**
```html
<!-- Store adds this one line to their website -->
<script src="https://widget.weedfinder.ai/embed.js" 
        data-api-url="https://api.weedfinder.ai"
        data-store-id="pend-oreille-cannabis"></script>
```

### Week 2: Deployment & ROI Tracking

**Fly.io Deployment**
```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

```bash
# Deploy to Fly.io
fly launch --name weedfinder-poc --region sea
fly secrets set OPENAI_API_KEY=sk-xxx POSABIT_TOKEN=xxx
fly deploy
```

**ROI Tracking Implementation**
```python
# roi_tracker.py
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText

class ROITracker:
    def __init__(self, db_url: str):
        self.conn = psycopg2.connect(db_url)
    
    def import_baseline_sales(self, csv_path: str):
        """Import last 30 days of sales data"""
        df = pd.read_csv(csv_path)
        df['closed_at'] = pd.to_datetime(df['closed_at'])
        
        # Store baseline (14 days before widget activation)
        cutoff = datetime.now() - timedelta(days=14)
        baseline = df[df['closed_at'] < cutoff]
        
        baseline.to_sql('sales_baseline', self.conn, if_exists='replace', index=False)
        
        baseline_aov = baseline['subtotal'].mean()
        print(f"Baseline AOV: ${baseline_aov:.2f}")
        return baseline_aov
    
    def calculate_current_lift(self):
        """Calculate basket lift vs baseline"""
        with self.conn.cursor() as cur:
            # Get baseline AOV
            cur.execute("SELECT AVG(subtotal) FROM sales_baseline")
            baseline_aov = cur.fetchone()[0]
            
            # Get current 7-day AOV (from live feed)
            cur.execute("""
                SELECT AVG(subtotal) 
                FROM sales_current 
                WHERE closed_at >= NOW() - INTERVAL '7 days'
            """)
            current_aov = cur.fetchone()[0] or baseline_aov
            
            lift_abs = current_aov - baseline_aov
            lift_pct = (lift_abs / baseline_aov) * 100 if baseline_aov > 0 else 0
            
            return {
                'baseline_aov': baseline_aov,
                'current_aov': current_aov,
                'lift_abs': lift_abs,
                'lift_pct': lift_pct
            }
    
    def send_weekly_report(self, store_email: str):
        """Send automated ROI email"""
        metrics = self.calculate_current_lift()
        
        # Estimate weekly revenue impact
        daily_tickets = 150  # Average for small dispensary
        weekly_impact = metrics['lift_abs'] * daily_tickets * 7
        
        email_body = f"""
WeedFinder Impact Report - Week Ending {datetime.now().strftime('%Y-%m-%d')}

💰 Average Basket:
Before Widget: ${metrics['baseline_aov']:.2f}
After Widget: ${metrics['current_aov']:.2f} (+{metrics['lift_pct']:.1f}%)

📈 Extra Revenue This Week: ${weekly_impact:.2f}

Method: Compares 14-day baseline to last 7 days using your POS export data.

Questions? Reply to this email or call support.
        """
        
        # Send email (simplified - use SendGrid in production)
        msg = MIMEText(email_body)
        msg['Subject'] = f"WeedFinder Weekly Impact: +${weekly_impact:.0f}"
        msg['From'] = "reports@weedfinder.ai"
        msg['To'] = store_email
        
        # Would implement actual email sending here
        print("Email sent:", email_body)
```

### Week 3: Store Integration & Testing

**Store Onboarding Process**
1. **Initial Meeting** (30 minutes)
   - Demo the widget live on their current menu
   - Explain ROI tracking methodology
   - Get POS export permissions (read-only API key or CSV)

2. **Technical Integration** (15 minutes)
   - Add widget script tag to their website
   - Test search functionality with real queries
   - Verify analytics tracking

3. **Baseline Setup** (5 minutes)
   - Import last 30 days of sales data
   - Calculate and confirm baseline AOV
   - Schedule first ROI report for Day 15

**Testing Checklist**
```bash
# Functional Tests
curl -X POST https://api.weedfinder.ai/search \
  -H "Content-Type: application/json" \
  -d '{"query": "something for sleep", "store_id": "pend-oreille"}'

# Performance Tests  
ab -n 100 -c 10 https://api.weedfinder.ai/ping

# Widget Integration Test
# Visit store website and verify:
# - Widget loads without errors
# - Search returns relevant results
# - Results display properly on mobile
```

### Week 4: Optimization & First Revenue

**Performance Optimization**
```python
# Add basic caching to reduce OpenAI costs
import redis
import hashlib

redis_client = redis.Redis.from_url(os.getenv('REDIS_URL'))

def cached_search(user_query: str, products: List[Dict]) -> Dict:
    # Create cache key from query + product hash
    products_hash = hashlib.md5(str(sorted([p['id'] for p in products])).encode()).hexdigest()
    cache_key = f"search:{hashlib.md5(user_query.encode()).hexdigest()}:{products_hash}"
    
    # Check cache first
    cached_result = redis_client.get(cache_key)
    if cached_result:
        return json.loads(cached_result)
    
    # Generate new result
    result = search_products(user_query, products)
    
    # Cache for 1 hour
    redis_client.setex(cache_key, 3600, json.dumps(result))
    
    return result
```

**Stripe Integration for First Payment**
```python
# billing.py
import stripe
from fastapi import HTTPException

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

def create_subscription(store_email: str, plan: str = "standard"):
    try:
        # Create customer
        customer = stripe.Customer.create(
            email=store_email,
            description=f"WeedFinder subscription - {plan}"
        )
        
        # Create subscription
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{
                'price': 'price_standard_49'  # $49/month price ID
            }],
            trial_period_days=14  # 14-day free trial
        )
        
        return {
            'subscription_id': subscription.id,
            'customer_id': customer.id,
            'trial_end': subscription.trial_end
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

## Success Criteria & Next Steps

### Week 4 Success Metrics
- [ ] Widget deployed and functional on store website
- [ ] Automated ROI email showing positive basket lift
- [ ] Store owner agrees to $49/month subscription
- [ ] Technical foundation ready for multi-store expansion
- [ ] Cost per query < $0.30 (before optimization)

### Transition to Phase 2 (MVP)
Once POC is successful:
1. **Canonical Schema**: Implement proper database schema for multi-store
2. **Vector Search**: Add pgvector for better search quality
3. **Multi-POS Support**: Build adapters for Cova, Dutchie, Flowhub
4. **Self-Service Onboarding**: Allow stores to sign up without manual setup
5. **Advanced Analytics**: Expand ROI tracking with more detailed metrics

### Risk Mitigation
- **Technical Failure**: Keep manual fallback for search queries
- **Store Rejection**: Offer 30-day money-back guarantee
- **Cost Overrun**: Implement query limits and caching from day 1
- **Competition**: Focus on speed to market and relationship building

### Resource Requirements
- **Time**: 40-60 hours over 4 weeks (10-15 hours/week)
- **Cost**: ~$100 (Fly.io, OpenAI, domain)
- **Skills**: Python, React, basic DevOps
- **External**: Store owner cooperation for integration and data access

---

*This POC phase establishes the foundation for all subsequent phases while proving core value with minimal investment.*
# Visit Tracking Configuration Guide

## Overview
The visit tracking system batches user visits and reports analytics to an external API every 30 minutes using a non-blocking background thread.

## Configuration

### Environment Variables
Add these to your `.env` file or production environment:

```bash
# Enable visit tracking
VISIT_TRACKING_ENABLED=true

# External API endpoint for analytics reporting
VISIT_TRACKING_API=https://your-analytics-api.com/v1/visits

# Reporting interval in seconds (default: 1800 = 30 minutes)
VISIT_TRACKING_INTERVAL=1800
```

### Flask Config (app/config.py)
```python
class Config:
    # Visit tracking settings
    VISIT_TRACKING_ENABLED = os.environ.get('VISIT_TRACKING_ENABLED', 'false').lower() == 'true'
    VISIT_TRACKING_API = os.environ.get('VISIT_TRACKING_API')
    VISIT_TRACKING_INTERVAL = int(os.environ.get('VISIT_TRACKING_INTERVAL', '1800'))
```

## API Payload Format

The system sends JSON payloads like this every 30 minutes:

```json
{
  "timestamp": "2026-01-25T14:30:00",
  "reporting_interval_seconds": 1800,
  "data": {
    "2026-01-25 14": {
      "count": 1523,
      "paths": {
        "/": 458,
        "/tools/floor-plan-analyzer/": 102,
        "/blog": 85
      },
      "user_agents": {
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...": 892,
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)...": 631
      },
      "countries": {
        "US": 650,
        "CA": 234,
        "GB": 189,
        "Unknown": 450
      }
    },
    "2026-01-25 15": {
      "count": 1102,
      ...
    }
  }
}
```

## Implementation Details

### Non-Blocking Architecture
- **before_request hook**: Captures visit metadata (path, user agent, country) in <1ms
- **Background thread**: Runs independently, reports every 30 minutes
- **Thread-safe batching**: Uses locks to prevent race conditions
- **Graceful shutdown**: Daemon thread terminates with app

### What's Tracked
- Visit count per hour bucket
- Popular paths (URL distribution)
- User agent breakdown (device types)
- Geographic distribution (from GeoIP)

### What's NOT Tracked
- Personal identifying information (PII)
- IP addresses
- Session cookies
- Form data
- Authentication tokens

## Security & Privacy

1. **Static files excluded**: `/static/*` paths ignored
2. **Health checks excluded**: `/health` endpoint ignored
3. **No PII**: User agents truncated to 100 chars, countries anonymized
4. **Memory bounded**: Data cleared after each successful report
5. **Fail-safe**: Tracking errors never crash requests

## Testing

### Enable in Development
```bash
export VISIT_TRACKING_ENABLED=true
export VISIT_TRACKING_API=https://httpbin.org/post  # Test endpoint
flask run
```

### View Logs
```bash
# You should see:
[INFO] Visit tracking initialized. Reporting to https://... every 1800s
[INFO] Sending visit report to https://...
[INFO] Visit report sent successfully: 2 time buckets
```

### Disable Tracking
```bash
export VISIT_TRACKING_ENABLED=false
# or simply don't set the environment variable
```

## Monitoring

### Check Background Thread
```python
# In Flask shell
from app.services.visit_tracker import BACKGROUND_THREAD
print(BACKGROUND_THREAD.is_alive())  # Should return True
```

### Manual Report Trigger (for testing)
```python
from app.services.visit_tracker import report_to_api
# Normally called automatically every 30 minutes
```

## API Integration Examples

### Simple Express.js Receiver
```javascript
const express = require('express');
const app = express();
app.use(express.json());

app.post('/v1/visits', (req, res) => {
  console.log('Received visit data:', req.body);
  // Store in database, send to analytics service, etc.
  res.json({ status: 'success' });
});

app.listen(3000);
```

### Python Flask Receiver
```python
from flask import Flask, request, jsonify
app = Flask(__name__)

@app.route('/v1/visits', methods=['POST'])
def receive_visits():
    data = request.get_json()
    print(f"Received {len(data['data'])} time buckets")
    # Process and store data
    return jsonify({'status': 'success'})
```

## Troubleshooting

### "No visit data to report"
- Normal if site had no traffic in the last 30 minutes
- Check Flask logs to ensure visits are being tracked

### "Failed to send visit report"
- Check API endpoint URL is correct and accessible
- Verify network connectivity from server
- Check API endpoint accepts JSON POST requests

### High Memory Usage
- Default batching clears data every 30 minutes
- Reduce `VISIT_TRACKING_INTERVAL` if needed
- Data structure is bounded by unique hour buckets (max 24 per day)

## Performance Impact

- **Request overhead**: <1ms per request (in-memory append)
- **Memory usage**: ~1-5 MB per 100k visits (before reporting)
- **Network**: 1 POST request every 30 minutes (~10-50 KB payload)
- **CPU**: Negligible (background thread sleeps between reports)

## Production Recommendations

1. Use a reliable analytics API endpoint with monitoring
2. Set up alerting if API returns errors
3. Consider using a message queue (RabbitMQ, Celery) for high-traffic sites
4. Implement API authentication (add headers in `report_to_api()`)
5. Monitor background thread health in production logs

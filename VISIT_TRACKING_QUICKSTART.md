# Quick Start: Enable Visit Tracking

## Production Environment Variables

Add these to your Render/Heroku/AWS environment:

```bash
VISIT_TRACKING_ENABLED=true
VISIT_TRACKING_API=https://your-analytics-api.com/v1/visits
VISIT_TRACKING_INTERVAL=1800
```

## Verify It's Working

### 1. Check Startup Logs
```
[INFO] Visit tracking initialized. Reporting to https://... every 1800s
```

### 2. Wait 30 Minutes, Check Reporting Logs
```
[INFO] Sending visit report to https://...
[INFO] Visit report sent successfully: 2 time buckets
```

### 3. Test API Endpoint (Development)
```bash
# Use httpbin.org for testing
export VISIT_TRACKING_API=https://httpbin.org/post
flask run

# Visit some pages, wait 30 minutes
# Check httpbin to see the POST payload
```

## Disable Tracking

```bash
# Option 1: Don't set VISIT_TRACKING_ENABLED
# Option 2: Explicitly disable
VISIT_TRACKING_ENABLED=false
```

## Sample API Receiver (Node.js)

```javascript
const express = require('express');
const app = express();
app.use(express.json());

app.post('/v1/visits', (req, res) => {
  const { timestamp, data } = req.body;
  console.log(`Received visit data at ${timestamp}`);
  
  // Process data (save to DB, forward to analytics, etc.)
  Object.entries(data).forEach(([hour, stats]) => {
    console.log(`${hour}: ${stats.count} visits`);
  });
  
  res.json({ status: 'success', received: Object.keys(data).length });
});

app.listen(3000, () => console.log('Analytics API running on port 3000'));
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No logs appearing | Check `VISIT_TRACKING_ENABLED=true` is set |
| API errors | Verify endpoint URL and accepts JSON POST |
| High memory | Reduce `VISIT_TRACKING_INTERVAL` to 900 (15 min) |

## Full Documentation

See [VISIT_TRACKING_GUIDE.md](./VISIT_TRACKING_GUIDE.md) for complete details.

# GPT Performance Metrics Implementation

## Backend Changes

### 1. GPTService (Car-Parts-Bot/app/services/gpt_service.py)
- Added class-level in-memory metrics:
  - `total_intent_checks`: Counter for total intent evaluations
  - `correct_intent_predictions`: Counter for correct predictions
  - `response_times`: List storing last 100 GPT API latencies

- Added methods:
  - `_record_latency(latency)`: Records GPT API response time
  - `record_intent_accuracy(intent, search_results)`: Tracks intent accuracy
  - `_is_intent_correct(intent, results)`: Evaluates if intent was correct

- Modified GPT API calls to track latency using `time.time()`

### 2. Admin API (Car-Parts-Bot/app/routes/admin.py)
- Added new endpoint: `GET /api/admin/metrics`
- Returns:
  ```json
  {
    "avg_latency": 0.523,
    "last_100_latencies": [0.5, 0.6, ...],
    "intent_accuracy_percent": 85.5,
    "correct_intents": 42,
    "total_intent_checks": 50
  }
  ```

### 3. Webhook Handler (Car-Parts-Bot/app/routes/webhook.py)
- Added call to `gpt_service.record_intent_accuracy()` after search results are obtained
- Tracks accuracy for every WhatsApp message processed

## Frontend Changes

### 1. API Service (src/services/api.js)
- Added `getMetrics()` method to fetch GPT performance data

### 2. Dashboard (src/pages/Dashboard.jsx)
- Added 4 new metric cards:
  - Average GPT Latency
  - Intent Accuracy %
  - Total Intents Evaluated
  - Correct Intents
- Added latency chart showing last 100 API calls
- Fetches metrics data on dashboard load

## Usage

1. Restart Flask backend to load changes
2. Restart Vite frontend dev server
3. Login with admin token
4. View real-time GPT performance metrics on dashboard

## Notes

- All metrics are stored in-memory (no database)
- Metrics reset when Flask server restarts
- Latency tracking limited to last 100 calls to prevent memory issues
- Accuracy tracking happens automatically for all WhatsApp messages

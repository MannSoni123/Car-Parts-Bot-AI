# Debugging "Sorry, we encountered an error" Message

## What This Error Means
This generic error message appears when an exception occurs in the `_process_user_message` function in webhook.py.

## How to Find the Real Error

### 1. Check Flask Console Logs
When you restart Flask, watch the console output. You should see:
```
Error processing message: [actual error here]
[full stack trace]
```

### 2. Common Errors and Solutions

#### Error: "No module named 'openai'"
**Solution:** Install OpenAI package
```bash
pip install openai
```

#### Error: "AuthenticationError" or "Invalid API key"
**Solution:** Check your OpenAI API key in .env
- Make sure OPENAI_API_KEY is set correctly
- Verify the key is valid (not expired)
- Test it at https://platform.openai.com/api-keys

#### Error: "RateLimitError"
**Solution:** You've exceeded OpenAI API quota
- Check your OpenAI account usage
- Add payment method if needed
- Wait for rate limit to reset

#### Error: "Connection refused" or "Database error"
**Solution:** Database connection issue
- Check MySQL is running
- Verify DB credentials in .env
- Test connection: `mysql -u root -p123456 carparts`

#### Error: "No such table: parts"
**Solution:** Database not initialized
```bash
flask db upgrade
```

#### Error: "'NoneType' object has no attribute..."
**Solution:** Missing configuration
- Check all required env vars are set
- Verify .env file is being loaded

## Steps to Debug

### Step 1: Restart Flask with Debug Mode
```bash
# In Car-Parts-Bot directory
python run.py
```

Watch the console output carefully.

### Step 2: Send a Test Message
Send "hi" via WhatsApp - this is the simplest message.

### Step 3: Check the Logs
Look for these log lines:
```
Message: hi
Intent: greeting, Entities: {}
```

If you see "Error processing message:", that's your actual error.

### Step 4: Fix Based on Error

**If you see GPT errors:**
- Check OPENAI_API_KEY in .env
- Verify the key works
- Check OpenAI account status

**If you see database errors:**
- Check MySQL is running
- Verify credentials
- Check tables exist

**If you see import errors:**
- Install missing packages
- Check virtual environment is activated

## Test Without WhatsApp

Create a simple test file `test_message.py`:
```python
from app import create_app
from app.routes.webhook import _process_user_message

app = create_app()

with app.app_context():
    result = _process_user_message("test_user", "hi")
    print(result)
```

Run it:
```bash
python test_message.py
```

This will show the exact error without needing WhatsApp.

## Quick Fixes

### Fix 1: Ensure .env is Loaded
Add to the top of run.py:
```python
from dotenv import load_dotenv
load_dotenv()
```

### Fix 2: Test OpenAI Key
```python
from openai import OpenAI
client = OpenAI(api_key="your-key-here")
try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "test"}]
    )
    print("OpenAI works!")
except Exception as e:
    print(f"OpenAI error: {e}")
```

### Fix 3: Test Database
```python
from app import create_app
from app.extensions import db
from app.models import Part

app = create_app()
with app.app_context():
    count = Part.query.count()
    print(f"Parts in database: {count}")
```

## After Fixing

1. Restart Flask server
2. Test with "hi" message
3. Then test with "PRT-1045"
4. Then test with "Toyota Corolla brake pads"

## Still Not Working?

Share the exact error from Flask console logs. The error message will tell us exactly what's wrong.

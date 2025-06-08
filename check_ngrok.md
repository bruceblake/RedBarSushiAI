# 🔍 NGROK TROUBLESHOOTING CHECKLIST

## 1. Check if ngrok is running:
```bash
# Run this in your terminal
curl http://localhost:4040/api/tunnels
```
**Expected output:** JSON with your tunnel info including the public URL

## 2. Check what URL ngrok is actually providing:
```bash
# Or check the ngrok web interface
open http://localhost:4040
```
**Look for:** The actual public URL (it might have changed!)

## 3. Check if your app is running locally:
```bash
# Test your local app
curl http://localhost:8000/healthcheck
# OR
curl http://localhost:3000/healthcheck
# OR whatever port your app runs on
```

## 4. Check which port ngrok is forwarding:
```bash
# Your ngrok command should look like:
ngrok http 8000
# OR
ngrok http 3000
# Make sure the port matches where your app is running
```

## 5. Test the webhook locally:
```bash
# If your app is on port 8000:
curl -X POST http://localhost:8000/voice/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "CallSid=CAtest&From=%2B15551234567&To=%2B17036467799&CallStatus=ringing"
```

## 🎯 QUICK FIXES:

### If ngrok URL changed:
1. Get new URL from `http://localhost:4040`
2. Update Twilio Console webhook URL
3. Test the new URL

### If app not running:
1. Start your FastAPI app:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### If wrong port:
1. Check what port your app runs on
2. Restart ngrok with correct port:
   ```bash
   ngrok http YOUR_APP_PORT
   ```

---

**Please run the commands above and let me know:**
1. What's the actual ngrok URL from `http://localhost:4040`?
2. Is your app responding locally?
3. What port is your app running on?
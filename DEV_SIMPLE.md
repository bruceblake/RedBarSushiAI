# Super Simple Development Guide

## First Time Setup (2 minutes)

1. **Add your API keys to `.env`**:
   ```bash
   nano .env
   ```
   Add these:
   - `OPENAI_API_KEY` - Get from https://platform.openai.com
   - `TWILIO_ACCOUNT_SID` - Get from Twilio Console
   - `TWILIO_AUTH_TOKEN` - Get from Twilio Console  
   - `TWILIO_PHONE_NUMBER` - Your Twilio number
   - `NGROK_AUTHTOKEN` - Get from https://ngrok.com

2. **Start everything**:
   ```bash
   ./dev.sh
   ```

That's it! The script will:
- Start PostgreSQL, Redis, and the app
- Initialize the database
- Show you the ngrok URL for Twilio

## Daily Development

### Start your day:
```bash
./dev.sh
```

### Check logs:
```bash
docker-compose -f docker-compose.dev.yml logs -f app
```

### Stop everything:
```bash
docker-compose -f docker-compose.dev.yml down
```

## That's ALL You Need!

- **Edit code**: Changes auto-reload
- **API Docs**: http://localhost:8000/docs
- **Test calls**: Use the ngrok URL shown by `./dev.sh`

## If Something Goes Wrong

```bash
# Nuclear reset
docker-compose -f docker-compose.dev.yml down -v
./dev.sh
```

---

Forget all the other scripts. Just use `./dev.sh` 🚀
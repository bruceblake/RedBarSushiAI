# Webhook Testing - RedBarSushiAI

## Webhook Configuration

The webhook URLs that Deliverect uses to communicate with RedBarSushiAI are:

- **statusUpdateURL**: `https://redbarsushiai.onrender.com/order_status`
- **menuUpdateURL**: `https://redbarsushiai.onrender.com/menu_update`
- **snoozeUnsnoozeURL**: `https://redbarsushiai.onrender.com/snoozeUnsnooze`
- **busyModeURL**: `https://redbarsushiai.onrender.com/busy_mode`
- **updatePrepTimeURL**: `https://redbarsushiai.onrender.com/updatePrepTime`
- **courierUpdateURL**: `https://redbarsushiai.onrender.com/courierUpdate`
- **paymentUpdateURL**: `https://redbarsushiai.onrender.com/payment_update`

## Testing Webhook Configuration

A diagnostic endpoint has been added to help test and debug webhook configuration:

```
https://redbarsushiai.onrender.com/webhook-test
```

This endpoint returns detailed information about:
- The current BASE_URL setting
- Environment configuration
- All webhook URLs
- Database connection status
- Registered locations count

## Common Issues & Solutions

### 1. Incorrect BASE_URL

**Symptoms**: 
- Webhooks showing PythonAnywhere URLs instead of Render URLs
- Deliverect not sending webhook events to your application

**Solution**:
- Set BASE_URL explicitly in environment variables:
  ```
  export BASE_URL=https://redbarsushiai.onrender.com
  ```
- Set DISABLE_PYTHONANYWHERE_DETECTION=true in environment
- Restart the application
- Check the webhook-test endpoint to verify the correct URLs

### 2. Registration Not Working

**Symptoms**:
- Unable to see webhook events in application logs
- Deliverect reports failed webhook calls

**Solution**:
1. Check logs during registration
2. Verify the register endpoint is returning proper URLs
3. Test webhook connectivity with the webhook-test endpoint
4. Make sure your server is accessible from the internet

### 3. Database Issues

**Symptoms**:
- Location not being stored properly
- "location not found" errors

**Solution**:
1. Check database connection in the webhook-test
2. Manually query the database to check location records
3. Re-register the location with Deliverect

## Monitoring Webhooks

For active monitoring of webhook activity, check:

1. Application logs for webhook requests:
   ```
   grep "webhook" /var/log/application.log
   ```

2. Endpoint access logs:
   ```
   grep "/order_status" /var/log/nginx/access.log
   ```

3. Database records for locations:
   ```sql
   SELECT * FROM location ORDER BY updated_at DESC LIMIT 10;
   ```
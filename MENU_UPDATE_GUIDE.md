# Deliverect Menu Update Guide

## Solving "Failed to save menu data" Error

If you're encountering the "Failed to save menu data" error when trying to publish menus from Deliverect, here are solutions:

### Solution 1: Use the Simplified Endpoint

We've added a simplified endpoint that always acknowledges the menu update without trying to save it to disk:

```
https://redbarsushiai.onrender.com/simple_menu_update
```

Configure Deliverect to send menu updates to this endpoint instead of the default `/menu_update` endpoint.

### Solution 2: Fix File Permissions

The error occurs when the application can't write to the menu file. Ensure proper permissions:

1. Check the current menu location:
   ```
   curl https://redbarsushiai.onrender.com/debug_menu
   ```

2. SSH into the server and fix permissions:
   ```bash
   # Find the menu file
   find /app -name "menu_data.json"
   
   # Make it writable
   chmod 644 /app/menu_data.json
   chmod 755 /app
   ```

### Solution 3: Check Docker Volume Configuration

If using Docker, ensure volumes are configured properly:

```yaml
services:
  web:
    volumes:
      - ./menu_data.json:/app/menu_data.json
```

### Enhanced Error Handling

We've improved error handling:

1. The application now attempts multiple backup paths when saving fails
2. Detailed logging of the save process for better debugging
3. A new `/debug_menu` endpoint that shows all possible menu paths

### Webhook Configuration in Deliverect

Set up your Deliverect webhooks as follows:

1. **Menu Webhook URL**: 
   - Primary: `https://redbarsushiai.onrender.com/menu_update`
   - Backup: `https://redbarsushiai.onrender.com/simple_menu_update`

2. **Status Webhook URLs:**
   ```
   statusUpdateURL: https://redbarsushiai.onrender.com/order_status
   menuUpdateURL: https://redbarsushiai.onrender.com/menu_update
   snoozeUnsnoozeURL: https://redbarsushiai.onrender.com/snoozeUnsnooze
   busyModeURL: https://redbarsushiai.onrender.com/busy_mode
   updatePrepTimeURL: https://redbarsushiai.onrender.com/updatePrepTime
   courierUpdateURL: https://redbarsushiai.onrender.com/courierUpdate
   paymentUpdateURL: https://redbarsushiai.onrender.com/payment_update
   ```

### Testing Menu Updates Locally

You can test menu updates locally to verify the menu processing works:

```bash
# Using curl
curl -X POST -H "Content-Type: application/json" \
  -d @test_data/deliverect_sample.json \
  https://redbarsushiai.onrender.com/simple_menu_update

# Using the test script
python test_menu_endpoint.py test_data/deliverect_sample.json https://redbarsushiai.onrender.com/simple_menu_update
```

## Troubleshooting

If issues persist, check these common problems:

1. **Disk Space**: Ensure there's enough disk space on the server
2. **Memory Issues**: Check for out-of-memory errors in the logs
3. **Docker Restart**: Sometimes a simple restart can fix permission issues:
   ```
   docker-compose restart web
   ```
4. **Log Analysis**: Check the application logs with:
   ```
   docker-compose logs -f web
   ```

## Support

For additional help, contact support or file an issue with:
- The complete error message
- Log output from the `/debug_menu` endpoint
- The payload you're trying to send (if possible)
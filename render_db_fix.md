# Render Database Migration Guide

This document explains how to add the SMS tracking fields to your Render-hosted database.

## The Problem

Your Render production database is missing the SMS tracking columns, causing errors like:

```
ERROR: column "sms_sid" of relation "order" does not exist
```

## Solution

You need to run the migration script on your Render database. Here's how:

### Option 1: Direct Connection from your computer

1. Get your Render database URL from the Render dashboard 
   - Go to your Render dashboard > Database > Connection tab
   - Copy the External Database URL

2. Run the migration script with the database URL:
   ```
   RENDER_DATABASE_URL="postgres://your-render-db-url" python migrate_sms_tracking_render.py
   ```

### Option 2: Deploy with the migration script

1. Use the special render migration script in this repo
   - Push the code including migrate_sms_tracking_render.py to GitHub

2. Connect to your Render instance via SSH and run:
   ```
   cd /app
   python migrate_sms_tracking_render.py
   ```

### Option 3: Run SQL commands manually

If the scripts don't work, you can run these SQL commands directly in the Render database shell:

1. Connect to your database from Render shell:
   ```
   psql $DATABASE_URL
   ```

2. Run the SQL commands:
   ```sql
   ALTER TABLE "order" ADD COLUMN sms_sid VARCHAR(50);
   ALTER TABLE "order" ADD COLUMN sms_status VARCHAR(20);
   ALTER TABLE "order" ADD COLUMN sms_error_code INTEGER;
   ALTER TABLE "order" ADD COLUMN sms_error_message VARCHAR(255);
   ```

## Verifying the Migration

After running the migration, verify the columns were added:

```sql
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'order' AND column_name LIKE 'sms%';
```

You should see four rows containing sms_sid, sms_status, sms_error_code, and sms_error_message.

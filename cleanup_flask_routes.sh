#!/bin/bash
# Script to safely archive Flask-specific routes

# Create an archive directory for Flask routes if it doesn't exist
mkdir -p archive/flask_routes

echo "Creating safe archive of Flask routes before removal..."

# Move app/routes/ to archive/flask_routes
echo "Archiving app/routes/ directory..."
cp -r app/routes/ archive/flask_routes/

# Create a cleanup summary file
echo "# Flask Routes Cleanup Summary" > FLASK_ROUTES_SUMMARY.md
echo "This file lists the Flask blueprints and routes that were archived during the migration to FastAPI." >> FLASK_ROUTES_SUMMARY.md
echo "" >> FLASK_ROUTES_SUMMARY.md
echo "## Archived Blueprints" >> FLASK_ROUTES_SUMMARY.md

# List all the blueprints in app/routes/
echo "Analyzing Flask blueprints..."
grep -r "Blueprint(" --include="*.py" app/routes/ | while read -r line; do
  file=$(echo "$line" | cut -d ":" -f 1)
  blueprint=$(echo "$line" | cut -d ":" -f 2)
  echo "- \`$blueprint\` - from $file" >> FLASK_ROUTES_SUMMARY.md
done

echo "" >> FLASK_ROUTES_SUMMARY.md
echo "## Archived Route Handlers" >> FLASK_ROUTES_SUMMARY.md

# List all the route handlers in app/routes/
echo "Analyzing Flask route handlers..."
grep -r "@.*route" --include="*.py" app/routes/ | while read -r line; do
  file=$(echo "$line" | cut -d ":" -f 1)
  route=$(echo "$line" | cut -d ":" -f 2)
  echo "- $route - from $file" >> FLASK_ROUTES_SUMMARY.md
done

echo "" >> FLASK_ROUTES_SUMMARY.md
echo "These routes have been migrated to FastAPI endpoints in the app/api/ directory." >> FLASK_ROUTES_SUMMARY.md

echo "Cleanup summary created in FLASK_ROUTES_SUMMARY.md"
echo "Flask routes have been archived to archive/flask_routes/"
echo "You can now safely delete the app/routes/ directory after verifying all routes have been migrated to FastAPI."
echo ""
echo "To delete the app/routes/ directory, run:"
echo "  rm -rf app/routes/"
echo ""
echo "IMPORTANT: Make sure you've migrated all essential routes to FastAPI before deletion!"
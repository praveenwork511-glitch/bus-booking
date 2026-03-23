#!/bin/bash
set -e

# Install dependencies
pip install -r requirements.txt

# Clear any cached Python files
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Flask should force template recompilation
export FLASK_ENV=production
export PYTHONDONTWRITEBYTECODE=1

echo "Build completed successfully"

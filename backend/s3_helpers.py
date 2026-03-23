"""
Template context processor for S3 URLs
"""

import os
from backend.s3_manager import get_s3_manager


def s3_url_for(filename):
    """
    Generate S3 URL for static files
    
    Usage in templates:
        <link rel="stylesheet" href="{{ s3_url_for('css/style.css') }}">
        <script src="{{ s3_url_for('js/app.js') }}"></script>
    
    Falls back to local URL if S3 not configured
    """
    if os.environ.get('AWS_ACCESS_KEY_ID'):
        try:
            s3_manager = get_s3_manager()
            s3_key = f"static/{filename}"
            
            # Use CloudFront if available, otherwise use S3
            return s3_manager.get_cloudfront_url(s3_key)
        except Exception as e:
            print(f"Warning: Could not generate S3 URL: {str(e)}")
            # Fall back to local URL
            return f"/static/{filename}"
    else:
        # No S3 configured, use local static files
        return f"/static/{filename}"


def register_s3_context(app):
    """Register S3 URL helper with Flask app"""
    @app.context_processor
    def inject_s3_url():
        return dict(s3_url_for=s3_url_for)

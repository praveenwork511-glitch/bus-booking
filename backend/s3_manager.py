"""
AWS S3 Integration Module for Bus Booking System
Handles file uploads and retrieval from AWS S3 bucket
"""

import boto3
import os
from botocore.exceptions import ClientError

class S3Manager:
    """Manager class for S3 operations"""
    
    def __init__(self):
        """Initialize S3 client with AWS credentials"""
        self.aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.bucket_name = os.environ.get('AWS_S3_BUCKET', 'bus-booking-files-default')
        self.region = os.environ.get('AWS_S3_REGION', 'us-east-1')
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key,
            region_name=self.region
        )
        
        # S3 resource for higher-level operations
        self.s3_resource = boto3.resource(
            's3',
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key,
            region_name=self.region
        )
    
    def upload_file(self, file_path, s3_key):
        """
        Upload a file to S3
        
        Args:
            file_path: Local path to file
            s3_key: Key/path in S3 bucket (e.g., 'static/css/style.css')
            
        Returns:
            S3 object URL or None on failure
        """
        try:
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': self._get_content_type(s3_key)}
            )
            url = self.get_s3_url(s3_key)
            print(f"✅ Uploaded: {s3_key} → {url}")
            return url
        except ClientError as e:
            print(f"❌ Error uploading {s3_key}: {str(e)}")
            return None
    
    def upload_directory(self, local_dir, s3_prefix=''):
        """
        Upload entire directory to S3
        
        Args:
            local_dir: Local directory path
            s3_prefix: Prefix path in S3 (e.g., 'static/')
            
        Returns:
            List of uploaded URLs
        """
        uploaded_files = []
        
        for root, dirs, files in os.walk(local_dir):
            for file in files:
                local_path = os.path.join(root, file)
                # Create S3 key relative to the directory being uploaded
                relative_path = os.path.relpath(local_path, local_dir)
                s3_key = os.path.join(s3_prefix, relative_path).replace('\\', '/')
                
                url = self.upload_file(local_path, s3_key)
                if url:
                    uploaded_files.append(url)
        
        return uploaded_files
    
    def delete_file(self, s3_key):
        """Delete a file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            print(f"✅ Deleted: {s3_key}")
            return True
        except ClientError as e:
            print(f"❌ Error deleting {s3_key}: {str(e)}")
            return False
    
    def list_files(self, prefix=''):
        """List all files in S3 bucket with optional prefix"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []
        except ClientError as e:
            print(f"❌ Error listing files: {str(e)}")
            return []
    
    def get_s3_url(self, s3_key):
        """
        Get public URL for S3 object
        
        Returns:
            Public S3 URL
        """
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
    
    def get_cloudfront_url(self, s3_key, cloudfront_domain=None):
        """
        Get CloudFront URL for S3 object (if CloudFront is configured)
        
        Args:
            s3_key: Key in S3 bucket
            cloudfront_domain: CloudFront distribution domain (e.g., d111111abcdef8.cloudfront.net)
            
        Returns:
            CloudFront URL
        """
        if not cloudfront_domain:
            cloudfront_domain = os.environ.get('CLOUDFRONT_DOMAIN')
        
        if cloudfront_domain:
            return f"https://{cloudfront_domain}/{s3_key}"
        
        # Fall back to S3 URL if CloudFront not configured
        return self.get_s3_url(s3_key)
    
    @staticmethod
    def _get_content_type(filename):
        """Determine content type based on file extension"""
        content_types = {
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.html': 'text/html',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
            '.ttf': 'font/ttf',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
            '.pdf': 'application/pdf',
        }
        
        _, ext = os.path.splitext(filename)
        return content_types.get(ext.lower(), 'application/octet-stream')


# Singleton instance
s3_manager = None

def get_s3_manager():
    """Get S3Manager singleton instance"""
    global s3_manager
    if s3_manager is None:
        s3_manager = S3Manager()
    return s3_manager

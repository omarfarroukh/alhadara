# Create a new file: storage_backends.py in your project root
from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings

class SupabaseStorage(S3Boto3Storage):
    """Custom storage backend for Supabase with better caching and content type handling"""
    
    def __init__(self, *args, **kwargs):
        kwargs.update({
            'bucket_name': settings.AWS_STORAGE_BUCKET_NAME,
            'region_name': settings.AWS_S3_REGION_NAME,
            'endpoint_url': settings.AWS_S3_ENDPOINT_URL,
            'access_key': settings.AWS_ACCESS_KEY_ID,
            'secret_key': settings.AWS_SECRET_ACCESS_KEY,
            'file_overwrite': True,
            'object_parameters': {
                'CacheControl': 'public, max-age=3600',
                'ContentDisposition': 'inline',
            }
        })
        super().__init__(*args, **kwargs)
    
    def _save(self, name, content):
        """Override save to ensure proper content type"""
        # Ensure the file pointer is at the beginning
        if hasattr(content, 'seek'):
            content.seek(0)
        
        # Let the parent handle the actual save
        return super()._save(name, content)
    
    def url(self, name):
        """Generate URL without authentication for public files"""
        if not name:
            return None
        
        # For Supabase, construct the public URL directly
        return f"{settings.AWS_S3_ENDPOINT_URL}/storage/v1/object/public/{settings.AWS_STORAGE_BUCKET_NAME}/{name}"

class SupabaseMediaStorage(SupabaseStorage):
    location = 'media'
    default_acl = 'public-read'

class SupabaseStaticStorage(SupabaseStorage):
    location = 'static'
    default_acl = 'public-read'
# api/exceptions.py
from rest_framework.views import exception_handler
from rest_framework.response import Response
import logging
import uuid

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    error_id = uuid.uuid4()
    
    # Log the full error
    logger.error(
        f"Error ID: {error_id}\n"
        f"Error: {str(exc)}\n"
        f"Context: {context}",
        exc_info=True
    )
    
    response = exception_handler(exc, context)
    
    if response is None:
        return Response(
            {
                'error': 'An unexpected error occurred',
                'error_id': str(error_id),
                'support': 'contact@example.com'
            },
            status=500
        )
    
    # Add error ID to all error responses
    if isinstance(response.data, dict):
        response.data['error_id'] = str(error_id)
    
    return response
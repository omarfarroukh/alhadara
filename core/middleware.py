# core/middleware.py
from django.utils.deprecation import MiddlewareMixin

class UTF8Middleware(MiddlewareMixin):
    def process_response(self, request, response):
        # Check if the response is JSON
        if response.get('Content-Type', '').startswith('application/json'):
            # Ensure charset=utf-8 is set
            if 'charset=utf-8' not in response['Content-Type'].lower():
                response['Content-Type'] = 'application/json; charset=utf-8'
        return response
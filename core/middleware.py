# core/middleware.py
from django.utils.deprecation import MiddlewareMixin
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model

User = get_user_model()

class UTF8Middleware(MiddlewareMixin):
    def process_response(self, request, response):
        # Check if the response is JSON
        if response.get('Content-Type', '').startswith('application/json'):
            # Ensure charset=utf-8 is set
            if 'charset=utf-8' not in response['Content-Type'].lower():
                response['Content-Type'] = 'application/json; charset=utf-8'
        return response

class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        # Get token from query string
        query_string = scope.get('query_string', b'').decode()
        query_params = dict(x.split('=') for x in query_string.split('&') if x)
        token = query_params.get('token', '')
        
        if token:
            try:
                # Validate JWT token
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                user = await self.get_user(user_id)
                scope['user'] = user
            except (InvalidToken, TokenError, User.DoesNotExist):
                scope['user'] = AnonymousUser()
        else:
            scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)
    
    @database_sync_to_async
    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return AnonymousUser()
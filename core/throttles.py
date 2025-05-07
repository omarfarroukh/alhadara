from rest_framework.throttling import SimpleRateThrottle

class LoginRateThrottle(SimpleRateThrottle):
    scope = 'login'  # Matches the 'login' key in your DEFAULT_THROTTLE_RATES
    
    def get_cache_key(self, request, view):
        # Use the IP address as the cache key
        ident = self.get_ident(request)
        
        # You can also use the username/phone from the request data to be more specific
        # This prevents an attacker from trying different credentials from the same IP
        phone = request.data.get('phone', '')
        if phone:
            return f"login_throttle_{ident}_{phone}"
        return f"login_throttle_{ident}"
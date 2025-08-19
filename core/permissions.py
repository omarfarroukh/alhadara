from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """
    Permission to only allow admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_staff

class IsAdminOrReception(permissions.BasePermission):
    """
    Allows access only to admin or reception users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_staff or request.user.user_type in ['admin', 'reception'])
        )
        
class IsOwnerOrAdminOrReception(permissions.BasePermission):
    """
    Object-level permission to allow owners, admins or reception staff.
    """
    def has_object_permission(self, request, view, obj):
        # Allow admin/reception
        if request.user.is_staff or request.user.user_type in ['admin', 'reception']:
            return True
            
        # Check if object has a user attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
            
        # Check if object has a user_id attribute
        if hasattr(obj, 'user_id'):
            return obj.user_id == request.user.id
            
        return False
    
class IsStudent(permissions.BasePermission):
    """
    Allows access only to student users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and 
                   request.user.user_type == 'student')

class IsTeacher(permissions.BasePermission):
    """
    Allows access only to teacher users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and 
                   request.user.user_type == 'teacher')

class IsReception(permissions.BasePermission):
    """
    Allows access only to reception staff.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and 
                   request.user.user_type == 'reception')

class IsAdmin(permissions.BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and 
                   (request.user.user_type == 'admin' or request.user.is_superuser))
        
class IsReceptionOrStudent(permissions.BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'user_type') and request.user.user_type in ['reception', 'student']

class IsTeacherOrReceptionOrAdmin(permissions.BasePermission):
    """
    Allows access only to teacher, reception, or admin users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.user_type in ['teacher', 'reception', 'admin']
        )
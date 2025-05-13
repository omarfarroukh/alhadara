from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """
    Permission to only allow admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_staff
class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object or admins to access it.
    """
    def has_object_permission(self, request, view, obj):
        # Admin permissions
        if request.user.is_staff:
            return True
            
        # Check if object has a user attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
            
        # Check if object has a requested_by attribute
        if hasattr(obj, 'requested_by'):
            return obj.requested_by == request.user
            
        # For Profile model
        if hasattr(obj, 'user_id'):
            return obj.user_id == request.user.id
            
        return False
    # permissions.py
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
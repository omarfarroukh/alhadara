from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied


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
    message = (
        "Your student account must be verified before you can perform this action. "
        "Please complete phone verification via Telegram and try again."
    )

    def has_object_permission(self, request, view, obj):
        user = request.user

        # 1. Admin / reception / teacher → always OK
        if user.is_staff or user.user_type in ['admin', 'reception', 'teacher']:
            return True

        # 2. Owner check
        owner = getattr(obj, 'user', None) or getattr(obj, 'user_id', None)
        if owner == user:
            # If owner is a student, enforce verification
            if user.user_type == 'student' and not user.is_verified:
                raise PermissionDenied(self.message)
            return True

        return False
    
class IsStudent(permissions.BasePermission):
    """
    Allow only verified students.
    """
    message = (
        "Your student account must be verified before you can perform this action. "
        "Please complete phone verification via Telegram and try again."
    )

    def has_permission(self, request, view):
        user = request.user
        if not (user.is_authenticated and user.user_type == 'student' and user.is_verified):
            raise PermissionDenied(self.message)
        return True

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
    message = (
        "Your student account must be verified before you can perform this action. "
        "Please complete phone verification via Telegram and try again."
    )

    def has_permission(self, request, view):
        user = request.user
        if not (hasattr(user, 'user_type') and user.is_authenticated):
            return False

        # Reception is always allowed
        if user.user_type == 'reception':
            return True

        # Student must be verified
        if user.user_type == 'student':
            if user.is_verified:
                return True
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(self.message)

        return False

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
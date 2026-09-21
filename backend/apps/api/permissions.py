from rest_framework import permissions


class IsTeacherUser(permissions.BasePermission):
    """
    Allows access only to authenticated teachers with an ACTIVE profile status,
    or administrators.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser or request.user.role == 'ADMIN':
            return True

        if request.user.role == 'TEACHER':
            if hasattr(request.user, 'teacher_profile'):
                profile = request.user.teacher_profile
                if profile.status != 'ACTIVE':
                    return False
                teacher_client = getattr(profile, 'client', None)
                if teacher_client is not None:
                    return teacher_client.uses_mobile_app
                org = getattr(request.user, 'organization', None)
                if org and not org.uses_mobile_app:
                    return False
                return True
        return False


class IsAssignedTeacher(permissions.BasePermission):
    """
    Object-level permission ensuring teachers can ONLY access students
    belonging to their explicitly assigned class and section within their organization.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        user_org = getattr(request.user, 'organization', None)
        user_org_id = user_org.id if user_org else None
        if obj.organization_id != user_org_id:
            return False

        if request.user.role == 'ADMIN':
            return True

        if not hasattr(request.user, 'teacher_profile'):
            return False

        profile = request.user.teacher_profile
        if not profile.assigned_class or not profile.assigned_section:
            return False

        teacher_client_id = getattr(profile, 'client_id', None)
        if teacher_client_id and getattr(obj, 'client_id', None) != teacher_client_id:
            return False

        return (
            obj.class_level_id == profile.assigned_class_id and
            obj.section_id == profile.assigned_section_id
        )

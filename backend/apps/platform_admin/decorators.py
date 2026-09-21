from functools import wraps
from django.shortcuts import redirect
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden
from django.template.response import TemplateResponse


def super_admin_required(view_func):
    """
    Decorator that strictly enforces Super Admin platform permissions.
    - If unauthenticated: redirects to Super Admin login (/platform-admin/login/).
    - If authenticated but not Super Admin (e.g. Teacher, Org Admin): returns HTTP 403 Forbidden.
    - If Super Admin: proceeds to the view.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('platform_admin:login')}?next={request.path}")

        # Check Super Admin status: is_superuser or role == 'SUPER_ADMIN'
        is_super = getattr(request.user, 'is_super_admin', None)
        if callable(is_super):
            has_perm = is_super()
        else:
            has_perm = request.user.is_superuser or getattr(request.user, 'role', '') == 'SUPER_ADMIN'

        if not has_perm:
            # Strictly forbidden for normal organization admins, teachers, and staff
            return HttpResponseForbidden(
                "403 Forbidden: Access Denied. This administrative portal is restricted to Platform Super Administrators only."
            )

        return view_func(request, *args, **kwargs)

    return _wrapped_view

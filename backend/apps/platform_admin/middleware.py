from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout
from django.http import JsonResponse
from apps.platform_admin.models import Organization


def get_user_organization(user):
    """
    Helper to resolve the organization for a user.
    Uses explicit ForeignKey user.organization, or fallback to linked School (id=1).
    """
    if not user or not user.is_authenticated:
        return None

    # Super admins are never bound to an org suspension
    is_super = getattr(user, 'is_super_admin', None)
    if (is_super and is_super()) or user.is_superuser or getattr(user, 'role', '') == 'SUPER_ADMIN':
        return None

    org = getattr(user, 'organization', None)
    if org:
        return org

    # Fallback to linked institution ORG-00001
    return Organization.objects.filter(school_id=1).first()


class OrganizationSuspensionMiddleware:
    """
    Middleware that enforces organization-level suspension in real-time.
    If an organization is SUSPENDED:
    - Normal administrators and staff belonging to that organization are blocked
      from accessing any organization-side views or APIs.
    - Super Admins (and Super Admins inspecting in Support Mode) remain completely unrestricted.
    - Platform-admin routes, static/media assets, and public routes are unaffected.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # 1. Bypass platform admin routes, Django admin, static, media, and logout
        if (path.startswith('/platform-admin/') or 
            path.startswith('/admin/') or 
            path.startswith('/static/') or 
            path.startswith('/media/') or
            path == '/logout/'):
            return self.get_response(request)

        # 2. Check if request has authenticated user (session-based)
        user = getattr(request, 'user', None)

        # Support DRF JWT authentication for /api/ routes
        if path.startswith('/api/') and (not user or not user.is_authenticated):
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                try:
                    from rest_framework_simplejwt.authentication import JWTAuthentication
                    jwt_auth = JWTAuthentication()
                    validated_token = jwt_auth.get_validated_token(auth_header.split()[1])
                    user = jwt_auth.get_user(validated_token)
                except Exception:
                    pass

        # 3. Check organization suspension
        org = get_user_organization(user)
        if org and org.status == 'SUSPENDED':
            error_message = (
                f"Access Denied: Organization '{org.name}' ({org.org_id}) has been "
                f"suspended by the platform administrator. Access to this system is temporarily locked."
            )

            # Block API requests with JSON 403
            if path.startswith('/api/'):
                return JsonResponse({
                    'error': 'organization_suspended',
                    'organization_id': org.org_id,
                    'message': error_message
                }, status=403)

            # Block web application requests
            # If user is hitting /login/, let the view handle/render
            if path == '/login/':
                return self.get_response(request)

            logout(request)
            messages.error(request, error_message)
            return redirect('admin_login')

        return self.get_response(request)

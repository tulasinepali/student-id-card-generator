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


class PortalSeparationMiddleware:
    """
    Strictly enforces separation between Platform Owner and Organization portals:
    - Platform Owners / Super Admins accessing organization routes without active Support Mode are redirected to the Platform Console.
    - Organization Admins accessing /platform-admin/ routes are blocked with HTTP 403 Forbidden.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Bypass static, media, API, public verification, root, and auth routes
        if (path.startswith('/static/') or 
            path.startswith('/media/') or 
            path.startswith('/api/') or 
            path.startswith('/verify/') or
            path.startswith('/admin/') or
            path in ('/', '/home/', '/login/', '/logout/', '/platform-admin/login/')):
            return self.get_response(request)

        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            is_super = getattr(user, 'is_super_admin', None)
            is_platform_super = is_super() if callable(is_super) else (user.is_superuser or getattr(user, 'role', '') == 'SUPER_ADMIN')

            # 1. If Platform Super Admin attempts to access organization routes directly:
            if is_platform_super and not path.startswith('/platform-admin/'):
                # Allow ONLY if currently in active Support Mode inspecting a tenant
                if not request.session.get('support_mode_org_id'):
                    messages.warning(
                        request,
                        "Access Denied: Platform Owner accounts cannot access the Organization Site directly. "
                        "You have been redirected to the Platform Console."
                    )
                    return redirect('platform_admin:dashboard')

            # 2. If Organization User attempts to access platform-admin routes:
            if not is_platform_super and path.startswith('/platform-admin/'):
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden("403 Forbidden: Organization accounts cannot access the Platform Portal.")

        return self.get_response(request)


from apps.platform_admin.models import Organization


def get_current_organization(request):
    """
    Returns the resolved organization for the current request.
    For superusers:
      1. Checks if currently in support session mode inspecting a tenant (support_mode_org_id in session).
      2. Falls back to request.user.organization if set.
      3. Falls back to Organization.objects.first() as default.
    For standard tenant users:
      Returns request.user.organization strictly.
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return None

    if request.user.is_superuser:
        support_id = request.session.get('support_mode_org_id') if hasattr(request, 'session') else None
        if support_id:
            support_org = Organization.objects.filter(id=support_id).first()
            if support_org:
                return support_org
        if getattr(request.user, 'organization', None):
            return request.user.organization
        return Organization.objects.first()

    return getattr(request.user, 'organization', None)

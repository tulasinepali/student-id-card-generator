from django.conf import settings
from apps.core.models import School
from apps.core.utils import get_current_organization


def school_settings_context(request):
    """Provides school singleton, multi-client studio context, and app configuration to all Django templates."""
    try:
        school = School.get_instance()
    except Exception:
        school = None

    active_client = None
    studio_clients = []
    is_studio = False
    org = get_current_organization(request)

    if org and getattr(org, 'is_studio', False):
        is_studio = True
        studio_clients = list(org.clients.filter(is_active=True).order_by('name'))
        active_client_id = request.session.get('active_client_id')
        if active_client_id:
            try:
                active_client = org.clients.filter(id=active_client_id).first()
            except Exception:
                request.session['active_client_id'] = None

    # Priority: Active Client School -> Current Organization School -> Default School Singleton
    if active_client and active_client.school:
        effective_school = active_client.school
    elif org:
        if not org.school:
            try:
                s = School.objects.create(
                    name=org.name,
                    short_name=org.short_name or org.name[:10],
                    address=org.address,
                    phone=org.phone,
                    email=org.email,
                    logo=org.logo
                )
                org.school = s
                org.save(update_fields=['school'])
            except Exception:
                pass
        effective_school = org.school if org.school else school
    else:
        effective_school = school

    effective_uses_mobile_app = True
    if active_client:
        effective_uses_mobile_app = getattr(active_client, 'uses_mobile_app', True)
    elif org:
        effective_uses_mobile_app = getattr(org, 'uses_mobile_app', True)

    return {
        'school': effective_school,
        'organization': org,
        'is_studio': is_studio,
        'studio_clients': studio_clients,
        'active_client': active_client,
        'active_client_id': active_client.id if active_client else None,
        'effective_uses_mobile_app': effective_uses_mobile_app,
        'app_config': {
            'name': settings.APP_NAME,
            'version': settings.APP_VERSION,
            'description': settings.APP_DESCRIPTION,
            'designer_name': settings.APP_DESIGNER_NAME,
            'designer_role': settings.APP_DESIGNER_ROLE,
            'contact_phone': settings.APP_CONTACT_PHONE,
            'contact_email': settings.APP_CONTACT_EMAIL,
            'website': settings.APP_WEBSITE,
            'copyright_year': settings.APP_COPYRIGHT_YEAR,
        }
    }


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

    # Global Platform Settings & Master Branding
    try:
        from apps.platform_admin.models import PlatformSetting
        platform_settings = PlatformSetting.get_instance()
    except Exception:
        platform_settings = None

    site_name = platform_settings.platform_name if platform_settings else settings.APP_NAME
    site_favicon = platform_settings.favicon.url if (platform_settings and platform_settings.favicon) else None
    site_copyright = platform_settings.copyright_text if platform_settings else f"© {settings.APP_COPYRIGHT_YEAR} {site_name}. All Rights Reserved."
    site_developed_by = platform_settings.developed_by if platform_settings else settings.APP_DESIGNER_NAME
    site_developed_by_url = platform_settings.developed_by_url if platform_settings else settings.APP_WEBSITE

    platform_unread_notifications_count = 0
    platform_latest_notifications = []
    if hasattr(request, 'user') and request.user.is_authenticated and (request.user.is_superuser or getattr(request.user, 'role', '') == 'SUPER_ADMIN'):
        try:
            from apps.platform_admin.models import PlatformNotification
            platform_unread_notifications_count = PlatformNotification.objects.filter(is_read=False).count()
            platform_latest_notifications = list(PlatformNotification.objects.all().order_by('-created_at')[:6])
        except Exception:
            pass

    return {
        'school': effective_school,
        'organization': org,
        'is_studio': is_studio,
        'studio_clients': studio_clients,
        'active_client': active_client,
        'active_client_id': active_client.id if active_client else None,
        'effective_uses_mobile_app': effective_uses_mobile_app,
        'platform_settings': platform_settings,
        'platform_unread_notifications_count': platform_unread_notifications_count,
        'platform_latest_notifications': platform_latest_notifications,
        'site_name': site_name,
        'site_favicon': site_favicon,
        'site_copyright': site_copyright,
        'site_developed_by': site_developed_by,
        'site_developed_by_url': site_developed_by_url,
        'app_config': {
            'name': platform_settings.app_name if platform_settings else settings.APP_NAME,
            'version': platform_settings.app_version if platform_settings else settings.APP_VERSION,
            'description': platform_settings.app_description if platform_settings else settings.APP_DESCRIPTION,
            'designer_name': site_developed_by,
            'designer_role': platform_settings.app_designer_role if platform_settings else settings.APP_DESIGNER_ROLE,
            'contact_phone': platform_settings.app_contact_phone if platform_settings else settings.APP_CONTACT_PHONE,
            'contact_email': platform_settings.app_contact_email if platform_settings else settings.APP_CONTACT_EMAIL,
            'website': site_developed_by_url,
            'copyright_year': site_copyright,
        }
    }



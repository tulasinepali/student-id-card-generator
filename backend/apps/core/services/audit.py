from apps.core.models import AuditLog


def get_client_ip(request):
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_action(user, action, object_type="", object_id="", object_repr="", details=None, request=None):
    """
    Centralized audit logging helper.
    Records user, action, affected object, metadata diffs, and client IP.
    """
    if details is None:
        details = {}
    
    ip_address = get_client_ip(request) if request else None

    # Do not log User instance directly if None or anonymous
    log_user = user if (user and user.is_authenticated) else None

    return AuditLog.objects.create(
        user=log_user,
        action=action,
        object_type=str(object_type),
        object_id=str(object_id),
        object_repr=str(object_repr)[:255],
        details=details,
        ip_address=ip_address
    )

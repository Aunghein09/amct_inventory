from functools import wraps

from django.http import HttpResponseForbidden

from .utils import user_has_role


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("Authentication required.")
            if not user_has_role(request.user, roles):
                return HttpResponseForbidden("You do not have permission for this action.")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator

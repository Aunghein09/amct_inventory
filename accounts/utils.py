from .models import Membership


def get_membership_for_user(user):
    if not user.is_authenticated:
        return None
    try:
        return user.membership
    except Membership.DoesNotExist:
        return None


def user_has_role(user, allowed_roles):
    membership = get_membership_for_user(user)
    return bool(membership and membership.role in allowed_roles)

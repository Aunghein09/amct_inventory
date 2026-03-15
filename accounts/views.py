from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


class CustomLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            next_url = request.GET.get("next", "/")
            return redirect(next_url)
        return super().get(request, *args, **kwargs)


@login_required
def post_login_redirect(request):
    return redirect("inventory:dashboard")

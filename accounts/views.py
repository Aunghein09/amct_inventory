from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


class CustomLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            next_url = request.GET.get("next")
            if next_url:
                return redirect(next_url)
            # Redirect based on which tab they originally logged in from
            login_dest = request.session.get("login_dest", "/")
            return redirect(login_dest)
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        # Store the intended destination in the session
        next_url = self.request.POST.get("next", "/")
        response = super().form_valid(form)
        self.request.session["login_dest"] = next_url
        return response


@login_required
def post_login_redirect(request):
    return redirect("inventory:dashboard")

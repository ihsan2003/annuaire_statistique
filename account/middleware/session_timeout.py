import datetime
from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect

class SessionIdleTimeout:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        current_datetime = datetime.datetime.now()
        last_activity = request.session.get('last_activity')

        if last_activity:
            elapsed = (current_datetime - datetime.datetime.fromisoformat(last_activity)).total_seconds()
            if elapsed > settings.SESSION_COOKIE_AGE:
                logout(request)
                return redirect('login')  

        request.session['last_activity'] = current_datetime.isoformat()
        return self.get_response(request)

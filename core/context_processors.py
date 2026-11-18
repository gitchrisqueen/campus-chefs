from django.conf import settings


def demo(request):
    return {"demo_mode": settings.CC_DEMO_MODE, "registration_open": settings.CC_REGISTRATION_OPEN}

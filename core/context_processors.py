from django.conf import settings


def demo(request):
    return {"demo_mode": settings.CC_DEMO_MODE}

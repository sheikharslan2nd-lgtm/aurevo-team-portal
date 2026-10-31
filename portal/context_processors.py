from django.conf import settings


def tool_access(request):
    return {
        "pakseo_tool_url": getattr(settings, "PAKSEO_TOOL_URL", "https://app.pakseotools.com/member"),
        "pakseo_tool_username": getattr(settings, "PAKSEO_TOOL_USERNAME", ""),
        "pakseo_tool_password": getattr(settings, "PAKSEO_TOOL_PASSWORD", ""),
    }

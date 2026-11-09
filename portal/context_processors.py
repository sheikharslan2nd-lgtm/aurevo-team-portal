def tool_access(request):
    # Credentials are never exposed to templates. Only a non-sensitive flag
    # indicating whether the integration has been configured is provided.
    try:
        from .models import ToolIntegrationConfig

        config = ToolIntegrationConfig.get_solo()
        ready = config.integration_ready
    except Exception:
        ready = False
    return {"tool_integration_configured": ready}
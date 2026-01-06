from fastapi import Header, HTTPException, status
import structlog

from src.core.config import settings as _settings

# Initialize global logger for the module
logger = structlog.get_logger(__name__)


async def verify_user(
    x_user_id: str = Header(None, alias="X-User-ID"), authorization: str = Header(None)
):
    """
    Dependency to simulate Azure AD Authentication.

    1. Local/Dev: Accepts 'X-User-ID' header or defaults to 'dev-user'.
    2. Production: Would validate the 'Authorization: Bearer <token>' JWT signature.
    """

    env = _settings.APP_ENV.lower()

    # Local
    if env != "production":
        # Allow bypassing auth for ease of testing
        user = x_user_id or "dev-user-001"
        logger.debug("auth_bypassed", env=env, user=user)
        return {"oid": user, "roles": ["admin"]}

    # Server - Not Tested
    if not authorization or not authorization.startswith("Bearer "):
        logger.warn("auth_failed", reason="missing_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Authorization header",
        )

    # Mock validation for the assignment (proving where the logic goes)
    token = authorization.split(" ")[1]
    if token == "invalid-token":
        raise HTTPException(status_code=401, detail="Token rejected")

    return {"oid": "azure-prod-user", "roles": ["user"]}

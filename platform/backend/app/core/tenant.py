from fastapi import HTTPException, status

VALID_TENANTS = ("development",)


def ensure_valid_tenant(tenant: str) -> str:
    if tenant not in VALID_TENANTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported tenant '{tenant}'. Expected one of: {', '.join(VALID_TENANTS)}",
        )
    return tenant

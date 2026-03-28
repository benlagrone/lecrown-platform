from fastapi import HTTPException, status

VALID_TENANTS = ("development", "properties")


def ensure_valid_tenant(tenant: str) -> str:
    if tenant not in VALID_TENANTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported tenant '{tenant}'. Expected one of: {', '.join(VALID_TENANTS)}",
        )
    return tenant


def ensure_properties_tenant(tenant: str) -> str:
    ensure_valid_tenant(tenant)
    if tenant != "properties":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Inquiry routes are limited to the properties tenant",
        )
    return tenant

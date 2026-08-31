from __future__ import annotations

from dataclasses import dataclass

import jwt

from app.config import get_settings

settings = get_settings()


class KeycloakAuthError(ValueError):
    pass


@dataclass(frozen=True)
class KeycloakIdentity:
    issuer: str
    subject: str
    email: str
    name: str
    roles: frozenset[str]


_jwks_clients: dict[str, jwt.PyJWKClient] = {}


def is_ready() -> bool:
    return settings.client_portal_auth_ready


def verify_access_token(token: str) -> KeycloakIdentity:
    if not is_ready():
        raise KeycloakAuthError("Client portal authentication is not configured")

    jwks_url = f"{settings.keycloak_issuer}/protocol/openid-connect/certs"
    jwks_client = _jwks_clients.setdefault(jwks_url, jwt.PyJWKClient(jwks_url, cache_keys=True))
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token.strip())
        claims = jwt.decode(
            token.strip(),
            signing_key.key,
            algorithms=["RS256", "RS384", "RS512"],
            issuer=settings.keycloak_issuer,
            options={
                "verify_aud": False,
                "require": ["exp", "iat", "iss", "sub"],
            },
        )
    except (jwt.PyJWTError, ValueError) as exc:
        raise KeycloakAuthError("Keycloak identity could not be verified") from exc

    authorized_party = str(claims.get("azp") or "").strip()
    audience_claim = claims.get("aud")
    audiences = (
        {str(value) for value in audience_claim}
        if isinstance(audience_claim, list)
        else {str(audience_claim or "")}
    )
    if settings.keycloak_client_id not in audiences and authorized_party != settings.keycloak_client_id:
        raise KeycloakAuthError("Token was not issued for the LeCrown client portal")

    subject = str(claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip().casefold()
    email_verified = claims.get("email_verified") is True
    roles = _extract_roles(claims)
    if not subject or not email or not email_verified:
        raise KeycloakAuthError("A verified client email is required")
    if not roles.intersection(settings.keycloak_allowed_roles):
        raise KeycloakAuthError("This Keycloak account does not have client portal access")

    return KeycloakIdentity(
        issuer=settings.keycloak_issuer,
        subject=subject,
        email=email,
        name=str(claims.get("name") or claims.get("preferred_username") or email).strip(),
        roles=frozenset(roles),
    )


def _extract_roles(claims: dict[str, object]) -> set[str]:
    roles: set[str] = set()
    realm_access = claims.get("realm_access")
    if isinstance(realm_access, dict):
        realm_roles = realm_access.get("roles")
        if isinstance(realm_roles, list):
            roles.update(str(role) for role in realm_roles if role)

    resource_access = claims.get("resource_access")
    if isinstance(resource_access, dict):
        client_access = resource_access.get(settings.keycloak_client_id)
        if isinstance(client_access, dict):
            client_roles = client_access.get("roles")
            if isinstance(client_roles, list):
                roles.update(str(role) for role in client_roles if role)
    return roles

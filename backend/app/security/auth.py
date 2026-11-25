"""Who is calling. Identity comes from a verified Supabase access token, the role from app.user_profiles."""
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..core.config import get_settings
from ..core.database import read
from ..core.errors import ApiError
from . import permissions

# Asymmetric only: with a shared secret this service could forge the tokens it verifies.
_ALGORITHMS = ["ES256", "RS256"]
_bearer = HTTPBearer(auto_error=False, description="Supabase access token")


@dataclass(frozen=True)
class Principal:
    """Also serves as Member 3's User: it reads `name` and `role` only."""
    user_id: str
    email: str
    name: str
    stored_role: str

    @property
    def role(self):
        return permissions.ROLE_NAMES[self.stored_role]


@lru_cache
def _jwks(url):
    return jwt.PyJWKClient(url, cache_jwk_set=True, lifespan=600, timeout=5)


def verify_token(token):
    settings = get_settings()
    if not settings.supabase_url:
        raise ApiError(503, "AUTH_UNAVAILABLE", "Authentication is not configured.")
    denied = ApiError(401, "UNAUTHENTICATED", "Sign in again.")
    try:
        if jwt.get_unverified_header(token).get("alg") not in _ALGORITHMS:
            raise denied
        key = _jwks(f"{settings.jwt_issuer}/.well-known/jwks.json").get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=_ALGORITHMS, audience="authenticated",
                            issuer=settings.jwt_issuer, leeway=10,
                            options={"require": ["exp", "sub", "aud", "iss"]})
    except jwt.PyJWKClientConnectionError as error:
        raise ApiError(503, "AUTH_UNAVAILABLE", "The sign-in service cannot be reached.") from error
    except (jwt.PyJWTError, ValueError) as error:
        raise denied from error
    return claims


def current_user(request: Request,
                 credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None) -> Principal:
    if credentials is None:
        raise ApiError(401, "UNAUTHENTICATED", "Sign in first.")
    claims = verify_token(credentials.credentials)
    with read() as db:
        profile = db.execute("SELECT email, full_name, role, is_active FROM app.user_profiles WHERE user_id::text = ?",
                             [claims["sub"]]).fetchone()
    if not profile or not profile["is_active"]:
        raise ApiError(403, "NO_ACCESS", "This account has no access. Ask an administrator.")
    request.state.user_id = claims["sub"]
    # A guest session is never more than a viewer, whatever its profile says.
    role = "VIEWER" if claims.get("is_anonymous") else profile["role"]
    return Principal(claims["sub"], profile["email"], profile["full_name"] or profile["email"] or "Guest", role)


def needs(permission):
    """Dependency: the caller, if their role holds the permission."""
    def check(user: Annotated[Principal, Depends(current_user)]):
        permissions.require(user, permission)
        return user
    return Depends(check)

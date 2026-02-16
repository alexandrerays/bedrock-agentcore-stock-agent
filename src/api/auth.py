"""Cognito JWT authentication middleware."""

import os
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from jose.exceptions import JWTClaimsError
import json
from urllib.request import urlopen
from functools import lru_cache


security = HTTPBearer()


@lru_cache(maxsize=1)
def get_cognito_public_keys() -> Dict[str, Any]:
    """
    Get Cognito public keys for JWT verification.
    Keys are cached to avoid repeated requests.
    """
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
    region = os.getenv("AWS_REGION", "us-east-1")

    if not user_pool_id:
        raise ValueError("COGNITO_USER_POOL_ID not set")

    # Construct JWKS URL
    jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"

    try:
        with urlopen(jwks_url) as response:
            keys = json.loads(response.read())
        return keys
    except Exception as e:
        print(f"Error fetching Cognito keys: {e}")
        raise


def verify_cognito_token(token: str) -> Dict[str, Any]:
    """
    Verify Cognito JWT token.

    Args:
        token: JWT token from Authorization header

    Returns:
        Decoded token claims

    Raises:
        HTTPException if token is invalid
    """
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
    region = os.getenv("AWS_REGION", "us-east-1")
    client_id = os.getenv("COGNITO_CLIENT_ID")

    if not all([user_pool_id, client_id]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cognito configuration missing"
        )

    try:
        # Get public keys
        keys = get_cognito_public_keys()

        # Decode without verification first to get the kid
        unverified = jwt.get_unverified_header(token)
        kid = unverified.get("kid")

        # Find the right key
        key = None
        for k in keys.get("keys", []):
            if k.get("kid") == kid:
                key = k
                break

        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find a signing key that matches"
            )

        # Verify and decode token
        decoded = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=client_id
        )

        return decoded

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    Get current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer token credentials

    Returns:
        User claims from token

    Raises:
        HTTPException if token is invalid or missing
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )

    try:
        token = credentials.credentials
        claims = verify_cognito_token(token)
        return claims
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


def get_user_id(user: Dict[str, Any] = Depends(get_current_user)) -> str:
    """Extract user ID from token claims."""
    return user.get("sub", user.get("cognito:username", "unknown"))


def verify_token_for_development(token: Optional[str] = None) -> Dict[str, Any]:
    """
    Verify token, with fallback for development.
    In development mode (if SKIP_AUTH env var is set), accepts any token.
    """
    skip_auth = os.getenv("SKIP_AUTH", "false").lower() == "true"

    if skip_auth:
        print("WARNING: Authentication disabled for development")
        return {"sub": "test-user", "cognito:username": "test-user"}

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token"
        )

    return verify_cognito_token(token)

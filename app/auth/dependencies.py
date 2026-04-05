from fastapi import HTTPException, Request, status

from app.auth.models import SessionUser


def get_session_user(request: Request) -> SessionUser | None:
    user_data = request.session.get("user")
    if not user_data:
        return None
    return SessionUser(**user_data)


def require_authorized_user(request: Request) -> SessionUser:
    user = get_session_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    if not user.authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to use this application",
        )

    return user

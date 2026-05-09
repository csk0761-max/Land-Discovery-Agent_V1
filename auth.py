from dataclasses import dataclass
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from services.supabase_service import supabase_service
from settings import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)

@dataclass(frozen=True)
class AuthContext:
    user_id: str
    email: str
    role: str
    token: str

def require_operator(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
        )
    
    token = credentials.credentials
    
    # Verify with Supabase
    try:
        if not supabase_service.is_available():
            # Fallback for dev if supabase is not configured
            return AuthContext(user_id="dev-user", email="dev@example.com", role="admin", token=token)
            
        user_response = supabase_service.client.auth.get_user(token)
        user = user_response.user
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
            
        return AuthContext(
            user_id=user.id,
            email=user.email,
            role="operator", # Default role, can be refined with database checks
            token=token
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )

def require_admin(auth: AuthContext = Depends(require_operator)):
    # For now, we'll allow all valid users to act as admins in this private beta
    # but we can add specific email or metadata checks here.
    return auth

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from datetime import datetime

from models.database import get_db
from models.legislation import User
from api.schemas.auth import (
    UserCreate, UserResponse, LoginRequest, Token,
    RefreshTokenRequest, UserUpdate
)
from api.auth.jwt_handler import jwt_handler
from api.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Register a new user

    **Requirements:**
    - Valid email address
    - Password (min 8 characters recommended)
    - Full name
    - Optional organization
    """

    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    # Hash password
    hashed_password = jwt_handler.get_password_hash(user_data.password)

    # Create new user
    db_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        organization=user_data.organization,
        is_active=True,
        is_verified=False,  # Email verification would be implemented
        created_at=datetime.utcnow()
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return UserResponse.from_orm(db_user)

@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login and get access tokens

    **Returns:**
    - Access token (30 min expiry)
    - Refresh token (7 day expiry)
    """

    # Authenticate user
    user = jwt_handler.authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Create tokens
    tokens = jwt_handler.create_tokens_for_user(user)

    return Token(**tokens)

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token

    **Note:** This invalidates the old refresh token and issues a new pair
    """

    # Verify refresh token
    payload = jwt_handler.verify_refresh_token(refresh_data.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user
    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Revoke old refresh token
    jwt_handler.revoke_refresh_token(user.id)

    # Create new tokens
    tokens = jwt_handler.create_tokens_for_user(user)

    return Token(**tokens)

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    authorization: str = Depends(security)
):
    """
    Logout user and blacklist current token

    **Note:** This blacklists the current access token and revokes refresh tokens
    """

    # Extract token from authorization header
    token = authorization.credentials

    # Blacklist access token
    jwt_handler.blacklist_token(token)

    # Revoke refresh token
    jwt_handler.revoke_refresh_token(current_user.id)

    return {"message": "Successfully logged out"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information"""
    return UserResponse.from_orm(current_user)

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user profile"""

    # Update fields
    for field, value in user_update.dict(exclude_unset=True).items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)

    return UserResponse.from_orm(current_user)

@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password"""

    # Verify old password
    if not jwt_handler.verify_password(old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )

    # Hash new password
    new_hashed_password = jwt_handler.get_password_hash(new_password)
    current_user.hashed_password = new_hashed_password

    db.commit()

    # Revoke all refresh tokens to force re-login
    jwt_handler.revoke_refresh_token(current_user.id)

    return {"message": "Password changed successfully"}

@router.post("/verify-token")
async def verify_token(
    current_user: User = Depends(get_current_user)
):
    """Verify if token is valid"""
    return {
        "valid": True,
        "user_id": current_user.id,
        "email": current_user.email
    }
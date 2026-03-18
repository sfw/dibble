from __future__ import annotations

import secrets
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter

from dibble.api.common import ApiContext, api_error
from dibble.models.auth import (
    BulkUserCreateRequest,
    BulkUserCreateResponse,
    User,
    UserCreateRequest,
    UserCreateResponse,
    UserSummary,
    UserUpdateRequest,
)
from dibble.services.auth import hash_credential
from dibble.services.passphrase import generate_passphrase


def _is_learner_role(role: str) -> bool:
    return role == "learner"


def _generate_credential(role: str) -> str:
    if _is_learner_role(role):
        return generate_passphrase(4)
    return secrets.token_urlsafe(32)


def _build_user(request: UserCreateRequest, credential: str) -> User:
    now = datetime.now(timezone.utc).isoformat()
    credential_hash = hash_credential(credential)
    return User(
        user_id=str(uuid4()),
        display_name=request.display_name,
        role=request.role,
        api_key_hash=credential_hash if not _is_learner_role(request.role) else None,
        passphrase_hash=credential_hash if _is_learner_role(request.role) else None,
        learner_id=request.learner_id,
        teacher_id=request.teacher_id,
        classroom_ids=request.classroom_ids,
        created_at=now,
        updated_at=now,
    )


def _user_to_summary(user: User) -> UserSummary:
    return UserSummary(
        user_id=user.user_id,
        display_name=user.display_name,
        role=user.role,
        learner_id=user.learner_id,
        teacher_id=user.teacher_id,
        classroom_ids=user.classroom_ids,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def build_user_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api/users", dependencies=context.deps("admin"))

    @router.post("", response_model=UserCreateResponse)
    def create_user(payload: UserCreateRequest) -> UserCreateResponse:
        credential = _generate_credential(payload.role)
        user = _build_user(payload, credential)
        context.services.user_store.create(user)
        return UserCreateResponse(
            user_id=user.user_id,
            credential=credential,
            display_name=user.display_name,
            role=user.role,
        )

    @router.get("", response_model=list[UserSummary])
    def list_users() -> list[UserSummary]:
        return [_user_to_summary(u) for u in context.services.user_store.list()]

    @router.get("/{user_id}", response_model=UserSummary)
    def get_user(user_id: str) -> UserSummary:
        user = context.services.user_store.get(user_id)
        if user is None:
            raise api_error(
                status_code=404, detail="User not found.", code="user_not_found"
            )
        return _user_to_summary(user)

    @router.put("/{user_id}", response_model=UserSummary)
    def update_user(user_id: str, payload: UserUpdateRequest) -> UserSummary:
        user = context.services.user_store.get(user_id)
        if user is None:
            raise api_error(
                status_code=404, detail="User not found.", code="user_not_found"
            )
        now = datetime.now(timezone.utc).isoformat()
        if payload.display_name is not None:
            user.display_name = payload.display_name
        if payload.role is not None:
            user.role = payload.role
        if payload.learner_id is not None:
            user.learner_id = payload.learner_id
        if payload.teacher_id is not None:
            user.teacher_id = payload.teacher_id
        if payload.classroom_ids is not None:
            user.classroom_ids = payload.classroom_ids
        user.updated_at = now
        context.services.user_store.update(user)
        return _user_to_summary(user)

    @router.delete("/{user_id}")
    def delete_user(user_id: str) -> dict[str, str]:
        deleted = context.services.user_store.delete(user_id)
        if not deleted:
            raise api_error(
                status_code=404, detail="User not found.", code="user_not_found"
            )
        return {"status": "deleted"}

    @router.post("/{user_id}/rotate-key", response_model=UserCreateResponse)
    def rotate_key(user_id: str) -> UserCreateResponse:
        user = context.services.user_store.get(user_id)
        if user is None:
            raise api_error(
                status_code=404, detail="User not found.", code="user_not_found"
            )
        credential = _generate_credential(user.role)
        credential_hash = hash_credential(credential)
        now = datetime.now(timezone.utc).isoformat()
        if _is_learner_role(user.role):
            user.passphrase_hash = credential_hash
        else:
            user.api_key_hash = credential_hash
        user.updated_at = now
        context.services.user_store.update(user)
        return UserCreateResponse(
            user_id=user.user_id,
            credential=credential,
            display_name=user.display_name,
            role=user.role,
        )

    @router.post("/bulk", response_model=BulkUserCreateResponse)
    def bulk_create_users(payload: BulkUserCreateRequest) -> BulkUserCreateResponse:
        results: list[UserCreateResponse] = []
        users_with_credentials: list[tuple[User, str]] = []
        for req in payload.users:
            credential = _generate_credential(req.role)
            user = _build_user(req, credential)
            users_with_credentials.append((user, credential))

        for user, credential in users_with_credentials:
            context.services.user_store.create(user)
            results.append(
                UserCreateResponse(
                    user_id=user.user_id,
                    credential=credential,
                    display_name=user.display_name,
                    role=user.role,
                )
            )
        return BulkUserCreateResponse(created=results)

    return router

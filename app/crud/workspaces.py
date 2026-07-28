from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WorkspaceRole
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate


async def get_workspace_by_id(db: AsyncSession, workspace_id: int) -> Workspace | None:
    """Return one workspace when it exists."""

    return await db.get(Workspace, workspace_id)


async def get_accessible_workspaces(
    db: AsyncSession,
    *,
    user_id: int,
    is_admin: bool,
) -> list[Workspace]:
    """Return workspaces visible through membership, unless the caller is an admin."""

    statement = select(Workspace).order_by(Workspace.id)
    if not is_admin:
        statement = statement.join(WorkspaceMember).where(WorkspaceMember.user_id == user_id)
    result = await db.scalars(statement)
    return list(result.all())


async def create_workspace(
    db: AsyncSession,
    workspace_in: WorkspaceCreate,
    owner_id: int,
) -> Workspace:
    """Create a workspace and its required owner membership atomically."""

    workspace = Workspace(name=workspace_in.name, owner_id=owner_id)
    db.add(workspace)
    try:
        await db.flush()
        db.add(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=owner_id,
                role=WorkspaceRole.OWNER,
            )
        )
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    await db.refresh(workspace)
    return workspace


async def update_workspace(
    db: AsyncSession,
    workspace: Workspace,
    workspace_in: WorkspaceUpdate,
) -> Workspace:
    """Apply supplied workspace fields and roll back a failed write."""

    for field_name, value in workspace_in.model_dump(exclude_unset=True).items():
        setattr(workspace, field_name, value)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    await db.refresh(workspace)
    return workspace


async def delete_workspace(db: AsyncSession, workspace: Workspace) -> None:
    """Delete a workspace and its cascading resources atomically."""

    await db.delete(workspace)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise


async def get_workspace_member(
    db: AsyncSession,
    workspace_id: int,
    user_id: int,
) -> WorkspaceMember | None:
    """Return a user's membership and role for one workspace."""

    result = await db.scalars(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    return result.one_or_none()


async def upsert_workspace_member(
    db: AsyncSession,
    *,
    workspace_id: int,
    user_id: int,
    role: WorkspaceRole,
) -> WorkspaceMember:
    """Invite a member or replace an existing non-owner membership role."""

    member = await db.get(WorkspaceMember, (workspace_id, user_id))
    if member is None:
        member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
        db.add(member)
    else:
        member.role = role
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    await db.refresh(member)
    return member


async def remove_workspace_member(db: AsyncSession, member: WorkspaceMember) -> None:
    """Remove one membership atomically."""

    await db.delete(member)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise

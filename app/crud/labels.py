from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.label import Label, TaskLabel
from app.models.project import Project
from app.models.workspace import WorkspaceMember
from app.schemas.label import LabelCreate, LabelUpdate


async def get_accessible_labels(
    db: AsyncSession,
    *,
    user_id: int,
    is_admin: bool,
) -> list[Label]:
    """Return labels only from projects the caller may read."""

    statement = select(Label).join(Project, Label.project_id == Project.id).order_by(Label.id)
    if not is_admin:
        statement = statement.join(
            WorkspaceMember,
            WorkspaceMember.workspace_id == Project.workspace_id,
        ).where(WorkspaceMember.user_id == user_id)
    result = await db.scalars(statement)
    return list(result.all())


async def get_labels_for_project(db: AsyncSession, project_id: int) -> list[Label]:
    """Return labels owned by one authorized project."""

    result = await db.scalars(
        select(Label).where(Label.project_id == project_id).order_by(Label.id)
    )
    return list(result.all())


async def get_label_for_project(
    db: AsyncSession,
    project_id: int,
    label_id: int,
) -> Label | None:
    """Return a label only when it belongs to the requested project."""

    result = await db.scalars(
        select(Label).where(Label.project_id == project_id, Label.id == label_id)
    )
    return result.one_or_none()


async def create_label(db: AsyncSession, project_id: int, label_in: LabelCreate) -> Label:
    """Create a label inside one authorized project."""

    label = Label(project_id=project_id, **label_in.model_dump())
    db.add(label)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    await db.refresh(label)
    return label


async def update_label(db: AsyncSession, label: Label, label_in: LabelUpdate) -> Label:
    """Apply supplied label fields atomically."""

    for field_name, value in label_in.model_dump(exclude_unset=True).items():
        setattr(label, field_name, value)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    await db.refresh(label)
    return label


async def delete_label(db: AsyncSession, label: Label) -> None:
    """Delete a label and cascading task-label links atomically."""

    await db.delete(label)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise


async def add_label_to_task(db: AsyncSession, task_id: int, label_id: int) -> None:
    """Create a task-label link when it does not already exist."""

    link = await db.get(TaskLabel, (task_id, label_id))
    if link is None:
        db.add(TaskLabel(task_id=task_id, label_id=label_id))
        try:
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            raise


async def remove_label_from_task(db: AsyncSession, task_id: int, label_id: int) -> bool:
    """Remove a task-label link and report whether it existed."""

    link = await db.get(TaskLabel, (task_id, label_id))
    if link is None:
        return False
    await db.delete(link)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    return True

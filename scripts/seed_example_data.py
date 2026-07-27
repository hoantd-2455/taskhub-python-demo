"""Create idempotent, non-production TaskHub data for local Swagger testing.

Run with: uv run python scripts/seed_example_data.py
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_password  # noqa: E402
from app.database import AsyncSessionLocal  # noqa: E402
from app.models.comment import Comment  # noqa: E402
from app.models.enums import (  # noqa: E402
    TaskPriority,
    TaskStatus,
    UserRole,
    WorkspaceRole,
)
from app.models.label import Label  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.models.task import Task  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.workspace import Workspace, WorkspaceMember  # noqa: E402

DEMO_PASSWORD = "TaskHubDemo123!"
WORKSPACE_NAME = "TaskHub Day 5 Demo"
PROJECT_NAME = "RBAC and Filtering"


async def get_or_create_user(
    email: str,
    full_name: str,
    role: UserRole,
) -> User:
    """Find a named demo user or create it with the known demo password."""

    async with AsyncSessionLocal() as session:
        async with session.begin():
            user = await session.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email,
                    full_name=full_name,
                    hashed_password=hash_password(DEMO_PASSWORD),
                    role=role,
                )
                session.add(user)
                await session.flush()
            else:
                user.full_name = full_name
                user.role = role
            return user


async def seed() -> None:
    """Create users, memberships, one project and varied tasks without duplicates."""

    await get_or_create_user("admin@taskhub.demo", "Demo Admin", UserRole.ADMIN)
    owner = await get_or_create_user("owner@taskhub.demo", "Demo Owner", UserRole.MEMBER)
    editor = await get_or_create_user("editor@taskhub.demo", "Demo Editor", UserRole.MEMBER)
    viewer = await get_or_create_user("viewer@taskhub.demo", "Demo Viewer", UserRole.MEMBER)
    await get_or_create_user("outsider@taskhub.demo", "Demo Outsider", UserRole.MEMBER)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            workspace = await session.scalar(
                select(Workspace).where(
                    Workspace.name == WORKSPACE_NAME,
                    Workspace.owner_id == owner.id,
                )
            )
            if workspace is None:
                workspace = Workspace(name=WORKSPACE_NAME, owner_id=owner.id)
                session.add(workspace)
                await session.flush()

            memberships = {
                owner.id: WorkspaceRole.OWNER,
                editor.id: WorkspaceRole.EDITOR,
                viewer.id: WorkspaceRole.VIEWER,
            }
            for user_id, role in memberships.items():
                membership = await session.get(WorkspaceMember, (workspace.id, user_id))
                if membership is None:
                    session.add(
                        WorkspaceMember(
                            workspace_id=workspace.id,
                            user_id=user_id,
                            role=role,
                        )
                    )
                else:
                    membership.role = role

            project = await session.scalar(
                select(Project).where(
                    Project.workspace_id == workspace.id,
                    Project.name == PROJECT_NAME,
                )
            )
            if project is None:
                project = Project(
                    workspace_id=workspace.id,
                    name=PROJECT_NAME,
                    description="Seed data for Day 5 role, filter and pagination exercises.",
                )
                session.add(project)
                await session.flush()

            labels = [("backend", "#2563EB"), ("security", "#DC2626")]
            for name, color in labels:
                label = await session.scalar(
                    select(Label).where(Label.project_id == project.id, Label.name == name)
                )
                if label is None:
                    session.add(Label(project_id=project.id, name=name, color=color))

            tasks = [
                (
                    "Define RBAC rules",
                    TaskStatus.TODO,
                    TaskPriority.HIGH,
                    owner.id,
                    date(2026, 8, 1),
                ),
                (
                    "Add task filters",
                    TaskStatus.IN_PROGRESS,
                    TaskPriority.MEDIUM,
                    editor.id,
                    date(2026, 8, 3),
                ),
                (
                    "Review API permissions",
                    TaskStatus.IN_REVIEW,
                    TaskPriority.HIGH,
                    editor.id,
                    None,
                ),
                ("Write pagination guide", TaskStatus.DONE, TaskPriority.LOW, viewer.id, None),
            ]
            for title, status, priority, assignee_id, due_date in tasks:
                task = await session.scalar(
                    select(Task).where(Task.project_id == project.id, Task.title == title)
                )
                if task is None:
                    task = Task(
                        project_id=project.id,
                        title=title,
                        status=status,
                        priority=priority,
                        assignee_id=assignee_id,
                        due_date=due_date,
                        created_by=owner.id,
                    )
                    session.add(task)
                    await session.flush()

            commented_task = await session.scalar(
                select(Task).where(
                    Task.project_id == project.id,
                    Task.title == "Review API permissions",
                )
            )
            if commented_task is not None:
                comment_content = (
                    "Editor note: verify that only authors, owners, and admins can delete comments."
                )
                comment = await session.scalar(
                    select(Comment).where(
                        Comment.task_id == commented_task.id,
                        Comment.content == comment_content,
                    )
                )
                if comment is None:
                    session.add(
                        Comment(
                            task_id=commented_task.id,
                            author_id=editor.id,
                            content=comment_content,
                        )
                    )

    print("Demo data is ready. See examples/day6-demo.md for accounts and Swagger requests.")


if __name__ == "__main__":
    asyncio.run(seed())

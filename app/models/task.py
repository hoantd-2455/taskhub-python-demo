from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TaskPriority, TaskStatus

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.label import Label
    from app.models.project import Project
    from app.models.user import User


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SqlEnum(TaskStatus, name="task_status", native_enum=False, create_constraint=True),
        default=TaskStatus.TODO,
        server_default=TaskStatus.TODO.value,
        nullable=False,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        SqlEnum(TaskPriority, name="task_priority", native_enum=False, create_constraint=True),
        default=TaskPriority.MEDIUM,
        server_default=TaskPriority.MEDIUM.value,
        nullable=False,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship(back_populates="tasks")
    assignee: Mapped["User | None"] = relationship(
        back_populates="assigned_tasks",
        foreign_keys=[assignee_id],
    )
    creator: Mapped["User"] = relationship(
        back_populates="created_tasks",
        foreign_keys=[created_by],
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )
    labels: Mapped[list["Label"]] = relationship(
        secondary="task_labels",
        back_populates="tasks",
    )

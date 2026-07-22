from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import projects as project_crud
from app.database import get_db
from app.schemas.project import ProjectResponse, ProjectWithTasksResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProjectResponse]:
    """List projects for the Day 2 CRUD exercise."""

    projects = await project_crud.get_projects(db)
    return [ProjectResponse.model_validate(project) for project in projects]


@router.get(
    "/{project_id}/tasks",
    response_model=ProjectWithTasksResponse,
    responses={404: {"description": "Project not found"}},
)
async def get_project_tasks(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectWithTasksResponse:
    """Get one project with its tasks eager-loaded to avoid N+1 queries."""

    project = await project_crud.get_project_with_tasks(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectWithTasksResponse.model_validate(project)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={404: {"description": "Project not found"}},
)
async def get_project(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectResponse:
    """Get one project by identifier."""

    project = await project_crud.get_project_by_id(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectResponse.model_validate(project)

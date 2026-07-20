from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import labels as label_crud
from app.database import get_db
from app.schemas.label import LabelResponse

router = APIRouter(prefix="/labels", tags=["labels"])


@router.get("", response_model=list[LabelResponse])
async def list_labels(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[LabelResponse]:
    """List labels for the Day 2 CRUD exercise."""

    labels = await label_crud.get_labels(db)
    return [LabelResponse.model_validate(label) for label in labels]

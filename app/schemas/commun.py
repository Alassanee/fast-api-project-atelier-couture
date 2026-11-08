"""Schémas communs : pagination {"items", "total", "limit", "offset"} (section 8)."""

from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel

LIMIT_DEFAUT = 20
LIMIT_MAX = 100


class Pagination(BaseModel):
    limit: int = LIMIT_DEFAUT
    offset: int = 0


def _pagination(
    limit: Annotated[int, Query(ge=1, le=LIMIT_MAX, description="Nombre d'éléments (max 100)")] = LIMIT_DEFAUT,
    offset: Annotated[int, Query(ge=0, description="Nombre d'éléments à sauter")] = 0,
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


PaginationParams = Annotated[Pagination, Depends(_pagination)]


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int

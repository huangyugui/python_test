from typing import Annotated

from fastapi import APIRouter, Depends

router = APIRouter()

async def common_parameters(q: str, skip: int = 0, limit: int = 100):
    return {"q": q, "skip": skip, "limit": limit}


@router.get("/depend")
async def depend0(commons: Annotated[dict, Depends(common_parameters)]):
    return commons

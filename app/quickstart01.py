from enum import Enum

import uvicorn
from fastapi import APIRouter

router = APIRouter()

@router.get("/shop")
async def shop():
    return {"message": "Hello World"}


class Country(str, Enum):
    china = "CN"
    america = "AME"
    france = "FR"

@router.get("/country/{country}")
async def country(country: Country):
    return {"message": f"Hello {country.name}"}

# 路径参数和查询参数并存
@router.get("/shop/{country}")
async def shop(country: str, need: bool, name: str = "名字"):
    return {"country": country, "need": need, "name": name}


if __name__ == '__main__':
    uvicorn.run("01_quickstart:app", host="0.0.0.0", port=8080, reload=True)
from typing import Annotated

import uvicorn
from fastapi import Query, Path, APIRouter
from pydantic import BaseModel, Field, field_validator

app = APIRouter()

class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None

@app.post("/item")
async def create_item(item: Item):
    str = item.name + " " +  (item.description if item.description is not None else "")
    print(str)
    return {"item": item.model_dump()}

# 同时支持路径，查询参数和请求体
@app.post("/items/{item_id}")
async def create_item(item_id: int, item: Item, request: bool):
    return {"item_id": item_id, "item": item.model_dump(), "request": request}


# Annotated校验
@app.post("/items2/{item_id}")
async def create_item(item_id: Annotated[int, Path(gt=3)],
                      item: Item,
                      request: bool,
                      name: Annotated[str| None, Query(title="查询参数name", max_length=3)]):
    return {"item_id": item_id, "item": item.model_dump(), "request": request, "name": name}


class FilterParams(BaseModel):
    model_config = {"extra": "forbid"} # 禁止额外的参数

    name: str | None = Field(None, title="姓名", min_length=1, max_length=100)
    age: int | None = Field(None, title="年龄", gt=1, lt=100)

# 如果使用了Query(), 则：http://127.0.0.1:8080/filter?name=1111&age=11
# 如果不加Query()， 则采用的是requestbody的方式
@app.post("/filter")
# async def create_filter(filter_params: Annotated[FilterParams, Query()]):
async def create_filter(filter_params: FilterParams):
    return filter_params.model_dump()


class Item(BaseModel):
    name: str
    age: int

    @field_validator("name")
    @classmethod
    def name_must_alpha(cls, value):
        assert value.isalpha(), f"{value} is not a valid name"
        return value

class User(BaseModel):
    name1: str
    age1: int

@app.post("/user/{user_id}")
async def create_user(user_id: int, user: User, item: Item, q: str|None = None):  # 默认q为查询参数，如果想嵌入到body中，需要使用Body()
    return {"user_id": user_id, "user": user.model_dump(), "item": item.model_dump(), "q": q}

# 任意dict构成的请求体
@app.post("/app/create")
async def create_item(item: dict[str, float|int ]):
    return item


if __name__ == '__main__':
    uvicorn.run("requestbody:app", host="127.0.0.1", port=8080, reload=True, debug=True)
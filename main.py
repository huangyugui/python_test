import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from app import (
    quickstart01,
    requestbody02,
    form03,
    depend04,
    stream05,
    sse06
)

app = FastAPI()

# 静态文件
app.mount("/static", StaticFiles(directory="statics"), name="static")

# 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins= ["*"],
    allow_credentials= True,
    allow_methods= ["*"],
    allow_headers= ["*"],
)

app.include_router(quickstart01.router, tags=["quickstart"])
app.include_router(requestbody02.app, tags=["requestbody"])
app.include_router(form03.router, tags=["form"])
app.include_router(depend04.router, tags=["depend"])
app.include_router(stream05.router, tags=["stream"])
app.include_router(sse06.router, tags=["sse"])


if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
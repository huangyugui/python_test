from typing import Annotated

from fastapi import APIRouter, Form, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import os

router = APIRouter()


@router.post("/region")
async def region(username: Annotated[str, Form()],
                 password: Annotated[str, Form()]
                 ):
    print(f'username: {username}, password: {password}')
    return {
        'username': username,
        'password': password
    }


class FormData(BaseModel):
    username: Annotated[str, Form(title="姓名", max_length=5, description="姓名1")]
    password: str

@router.post("/login")
async def login(user: Annotated[FormData, Form()]):

    return {
        'username': user.username
    }


@router.post("/upload")
async def upload(file: UploadFile):
    path = os.path.join("app", "img", file.filename)
    print("path: ", path)
    with open(path, "wb") as f:
        for line in file.file:
            f.write(line)

    return {
        "fileName": file.filename
    }

@router.post("/user-form")
async def user_form_submit(
        name: Annotated[str, Form(min_length=1, max_length=20)],
        age: Annotated[int, Form(ge=0, le=150)],
        avatar: UploadFile,
):
    avatar_dir = os.path.join("app", "img")
    os.makedirs(avatar_dir, exist_ok=True)
    avatar_path = os.path.join(avatar_dir, avatar.filename)
    with open(avatar_path, "wb") as f:
        for line in avatar.file:
            f.write(line)

    return {
        "name": name,
        "age": age,
        "avatarFileName": avatar.filename,
        "avatarSavedPath": avatar_path,
    }


class UserFormModel(BaseModel):
    name: str = Field(min_length=1, max_length=20, description="姓名")
    age: int = Field(ge=0, le=150, description="年龄")
    email: str | None = None
    phone: str | None = None
    remark: str | None = None


@router.post("/user-form-model")
async def user_form_model_submit(
        form: Annotated[UserFormModel, Form()],
        avatar: UploadFile,
):
    avatar_dir = os.path.join("app","img")
    os.makedirs(avatar_dir, exist_ok=True)
    avatar_path = os.path.join(avatar_dir, avatar.filename)
    with open(avatar_path, "wb") as f:
        for line in avatar.file:
            f.write(line)

    return {
        "form": form.model_dump(),
        "avatarFileName": avatar.filename,
        "avatarSavedPath": avatar_path,
    }

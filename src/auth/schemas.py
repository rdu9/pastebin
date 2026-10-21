from pydantic import BaseModel


class UserCreateModel(BaseModel):
    email: str
    password: str

class UserLoginModel(BaseModel):
    email: str
    password: str

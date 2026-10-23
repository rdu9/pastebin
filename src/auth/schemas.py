from pydantic import BaseModel, EmailStr


class UserCreateModel(BaseModel):
    email: EmailStr
    password: str

class UserLoginModel(BaseModel):
    email: EmailStr
    password: str

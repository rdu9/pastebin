from pydantic import BaseModel, EmailStr, Field


class UserCreateModel(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class UserLoginModel(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)

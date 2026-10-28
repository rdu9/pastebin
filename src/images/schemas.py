import uuid
from typing import Literal
from pydantic import BaseModel, Field

MAX_IMAGE_BYTES = 5*1024*1024

class UploadUrlRequest(BaseModel,extra="forbid"):
    paste_uid: uuid.UUID
    content_type: Literal["image/png","image/jpeg","image/webp","image/gif"]
    size_bytes: int = Field(gt=0,le=MAX_IMAGE_BYTES)

from pydantic import BaseModel, Field
from src.db.models import Visibility
from typing import Literal



class PasteCreateModel(BaseModel):
    title: str | None = None
    content: str = Field(min_length=1,max_length=512_000)
    language: str | None = None
    visibility: Visibility = Visibility.unlisted
    burn_after_reading: bool = False
    expires_in: Literal["1h", "1d", "1w", "never"] = "never"

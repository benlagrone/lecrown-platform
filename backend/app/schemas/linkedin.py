from pydantic import BaseModel, Field


class LinkedInPublishRequest(BaseModel):
    content_id: str = Field(min_length=1)


class LinkedInPublishResponse(BaseModel):
    status: str
    content_id: str
    linkedin: dict

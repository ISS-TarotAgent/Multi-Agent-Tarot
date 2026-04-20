from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PersistenceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

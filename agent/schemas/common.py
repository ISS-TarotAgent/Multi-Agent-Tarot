from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AgentSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

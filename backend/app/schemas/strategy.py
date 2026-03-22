from pydantic import BaseModel, Field


class ToolResponsibility(BaseModel):
    tool: str
    role: str
    owns: list[str] = Field(default_factory=list)


class StrategyTrack(BaseModel):
    id: str
    name: str
    horizon: str
    goal: str
    current_focus: str


class StrategyMetric(BaseModel):
    label: str
    value: int


class StrategySnapshot(BaseModel):
    tracks: list[StrategyTrack]
    tools: list[ToolResponsibility]
    linear_project: str
    linear_epics: list[str] = Field(default_factory=list)
    weekly_loop: list[str] = Field(default_factory=list)
    metrics: list[StrategyMetric] = Field(default_factory=list)

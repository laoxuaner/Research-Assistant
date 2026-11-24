from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class ProjectInput(Input):
    name: str = Field(min_length=1,max_length=200)
    question: str = Field(default="",max_length=10000)
    hypothesis: str = Field(default="",max_length=10000)
    tags: list[str] = Field(default_factory=list,max_length=30)
    notes: str = Field(default="",max_length=30000)
    archived: bool = False

class ProjectPatch(Input):
    name: str | None = Field(default=None,min_length=1,max_length=200)
    question: str | None = Field(default=None,max_length=10000)
    hypothesis: str | None = Field(default=None,max_length=10000)
    tags: list[str] | None = Field(default=None,max_length=30)
    notes: str | None = Field(default=None,max_length=30000)
    archived: bool | None = None

class PaperPatch(Input):
    title: str | None = Field(default=None,min_length=1,max_length=500)
    authors: str | None = Field(default=None,max_length=2000)
    year: int | None = Field(default=None,ge=1000,le=2200)
    doi: str | None = Field(default=None,max_length=300)
    tags: list[str] | None = Field(default=None,max_length=30)
    reading_status: Literal["unread","reading","read"] | None = None
    notes: str | None = Field(default=None,max_length=50000)

class SearchInput(Input):
    query: str = Field(min_length=1,max_length=2000)
    paper_ids: list[str] = Field(default_factory=list,max_length=100)
    year: int | None = None
    tags: list[str] = Field(default_factory=list,max_length=30)
    limit: int = Field(default=8,ge=1,le=30)

class AskInput(Input):
    question: str = Field(min_length=1,max_length=2000)
    paper_ids: list[str] = Field(default_factory=list,max_length=100)
    conversation_id: str | None = None

class CompareInput(Input):
    paper_ids: list[str] = Field(min_length=2,max_length=5)
    @model_validator(mode="after")
    def unique(self):
        if len(set(self.paper_ids))!=len(self.paper_ids): raise ValueError("请选择不同论文")
        return self

class ExperimentInput(Input):
    name: str = Field(min_length=1,max_length=200)
    hypothesis: str = Field(default="",max_length=10000)
    paper_ids: list[str] = Field(default_factory=list,max_length=100)
    conditions: str = Field(default="",max_length=10000)
    parameters: str = Field(default="",max_length=10000)
    notes: str = Field(default="",max_length=30000)

class CleanInput(Input):
    drop_missing_columns: list[str] = Field(default_factory=list,max_length=200)
    drop_duplicate_rows: bool = False

class SuggestInput(Input):
    dataset_id: str
    question: str = Field(default="",max_length=2000)

class ReportInput(Input):
    analysis_id: str
    title: str = Field(default="",max_length=200)

class SettingsInput(Input):
    ai_enabled: bool

class NoteInput(Input):
    content: str = Field(max_length=50000)
    paper_id: str | None = None

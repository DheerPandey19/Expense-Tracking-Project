from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


def _normalize_tag_names(names: list[str] | None) -> list[str] | None:
    if names is None:
        return None
    seen: set[str] = set()
    out: list[str] = []
    for raw in names:
        name = " ".join(raw.strip().split()).lower()
        if not name or name in seen:
            continue
        if len(name) > 40:
            raise ValueError("each tag must be at most 40 characters")
        seen.add(name)
        out.append(name)
    return out


def _dedupe_ids(ids: list[int]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for i in ids:
        if i in seen:
            continue
        seen.add(i)
        out.append(i)
    return out


class ExpenseCreate(BaseModel):
    category_id: int | None = None
    category_ids: list[int] | None = None
    amount: float = Field(gt=0)
    date: Date | None = None
    note: str = Field(default="", max_length=240)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_create_tags(cls, v: object) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("tags must be a list of strings")
        return _normalize_tag_names([str(x) for x in v]) or []

    @model_validator(mode="after")
    def resolve_category_ids(self) -> "ExpenseCreate":
        ids = list(self.category_ids or [])
        if self.category_id is not None:
            ids = [self.category_id, *[i for i in ids if i != self.category_id]]
        ids = _dedupe_ids(ids)
        if not ids:
            raise ValueError("at least one category is required")
        self.category_ids = ids
        self.category_id = ids[0]
        return self


class ExpenseUpdate(BaseModel):
    category_id: int | None = None
    category_ids: list[int] | None = None
    amount: float | None = Field(default=None, gt=0)
    date: Date | None = None
    note: str | None = Field(default=None, max_length=240)
    tags: list[str] | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_update_tags(cls, v: object) -> list[str] | None:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("tags must be a list of strings")
        return _normalize_tag_names([str(x) for x in v])

    @model_validator(mode="after")
    def resolve_category_ids(self) -> "ExpenseUpdate":
        if self.category_ids is None and self.category_id is None:
            return self
        ids = list(self.category_ids or [])
        if self.category_id is not None:
            ids = [self.category_id, *[i for i in ids if i != self.category_id]]
        ids = _dedupe_ids(ids)
        if not ids:
            raise ValueError("at least one category is required")
        self.category_ids = ids
        self.category_id = ids[0]
        return self


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    amount: float
    date: Date
    note: str
    category_name: str | None = None
    categories: list[CategoryOut] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class CategoryTotal(BaseModel):
    category_id: int
    name: str
    total: float
    color: str | None = None


class SummaryOut(BaseModel):
    total_spend: float
    by_category: list[CategoryTotal]


class ParseIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class ExpenseDraft(BaseModel):
    amount: float = Field(gt=0)
    category_id: int | None = None
    category_ids: list[int] = Field(default_factory=list)
    date: Date | None = None
    note: str = ""
    confidence: str = "low"
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_category_ids(self) -> "ExpenseDraft":
        if self.category_ids:
            self.category_ids = _dedupe_ids(self.category_ids)
            if self.category_id is None:
                self.category_id = self.category_ids[0]
            return self
        if self.category_id is not None:
            self.category_ids = [self.category_id]
        return self


class ParseOut(BaseModel):
    drafts: list[ExpenseDraft]


class BudgetUpsert(BaseModel):
    category_id: int
    amount: float = Field(gt=0)


class BudgetProgress(BaseModel):
    category_id: int
    category_name: str
    color: str
    limit: float
    spent: float
    remaining: float
    over: bool
    pct: float

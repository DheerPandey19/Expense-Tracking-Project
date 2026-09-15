from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class ExpenseCreate(BaseModel):
    category_id: int
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


class ExpenseUpdate(BaseModel):
    category_id: int | None = None
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


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    amount: float
    date: Date
    note: str
    category_name: str | None = None
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
    date: Date | None = None
    note: str = ""
    confidence: str = "low"
    tags: list[str] = Field(default_factory=list)


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

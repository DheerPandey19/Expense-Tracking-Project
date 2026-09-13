from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str


class ExpenseCreate(BaseModel):
    category_id: int
    amount: float = Field(gt=0)
    date: Date | None = None
    note: str = Field(default="", max_length=240)


class ExpenseUpdate(BaseModel):
    category_id: int | None = None
    amount: float | None = Field(default=None, gt=0)
    date: Date | None = None
    note: str | None = Field(default=None, max_length=240)


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    amount: float
    date: Date
    note: str
    category_name: str | None = None


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


class ParseOut(BaseModel):
    drafts: list[ExpenseDraft]

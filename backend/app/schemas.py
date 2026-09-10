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


class SummaryOut(BaseModel):
    total_spend: float
    by_category: list[CategoryTotal]

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CategoryOut(BaseModel):
    id: int
    name: str
    color: str
    icon: str
    enabled: bool
    expectedMonthly: float = Field(serialization_alias="expectedMonthly")

    model_config = {"from_attributes": True, "populate_by_name": True}

    @classmethod
    def from_orm_model(cls, cat) -> "CategoryOut":
        return cls(
            id=cat.id,
            name=cat.name,
            color=cat.color,
            icon=cat.icon,
            enabled=cat.enabled,
            expectedMonthly=cat.expected_monthly,
        )


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#64748b", max_length=16)


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    color: Optional[str] = None
    enabled: Optional[bool] = None
    expectedMonthly: Optional[float] = Field(default=None, ge=0)


class ExpenseOut(BaseModel):
    id: int
    amount: float
    categoryId: int
    date: date
    note: str
    source: str
    createdAt: Optional[str] = None


class ExpenseCreate(BaseModel):
    amount: float = Field(gt=0)
    categoryId: int
    date: date
    note: str = ""
    source: Literal["chat", "manual"] = "manual"


class ExpenseUpdate(BaseModel):
    amount: Optional[float] = Field(default=None, gt=0)
    categoryId: Optional[int] = None
    date: Optional[date] = None
    note: Optional[str] = None


class ParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class ParseDraft(BaseModel):
    amount: Optional[float] = None
    categoryId: Optional[int] = None
    date: date
    note: str = ""
    confidence: float = 0.5
    warning: Optional[str] = None


class ParseResponse(BaseModel):
    drafts: list[ParseDraft]
    usedLlm: bool = False


class CategorySummary(BaseModel):
    categoryId: int
    name: str
    color: str
    enabled: bool
    expected: float
    actual: float
    variance: Optional[float] = None


class SummaryOut(BaseModel):
    month: str
    daysElapsed: int
    daysInMonth: int
    totalSpent: float
    totalExpected: float
    projectedMonthEnd: float
    categories: list[CategorySummary]


class SettingsOut(BaseModel):
    currency: str
    llmConfigured: bool


class SettingsUpdate(BaseModel):
    currency: Optional[str] = Field(default=None, min_length=1, max_length=8)

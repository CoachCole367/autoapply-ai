from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Applicant(BaseModel):
    name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=300)
    phone: str = Field(default="", max_length=60)
    location: str = Field(default="", max_length=300)
    skills: list[str] = Field(default_factory=list, max_length=200)
    experience: list[str] = Field(default_factory=list, max_length=100)
    education: list[str] = Field(default_factory=list, max_length=100)
    certifications: list[str] = Field(default_factory=list, max_length=100)
    preferred_titles: list[str] = Field(default_factory=list)
    allowed_locations: list[str] = Field(default_factory=list)
    authorized_countries: list[str] = Field(default_factory=list)
    minimum_salary: int | None = Field(default=None, ge=0)
    answers: dict[str, str] = Field(default_factory=dict)
    verified: bool = False


class Policy(BaseModel):
    enabled: bool = False
    emergency_stop: bool = False
    dry_run: bool = True
    auto_submit: bool = False
    minimum_score: int = Field(default=85, ge=0, le=100)
    review_score: int = Field(default=65, ge=0, le=100)
    daily_cap: int = Field(default=10, ge=0, le=100)
    interval_hours: int = Field(default=6, ge=1, le=168)
    allowed_hosts: list[str] = Field(default_factory=list)
    blocked_employers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def thresholds(self):
        if self.review_score > self.minimum_score:
            raise ValueError("Review threshold must not exceed automatic threshold")
        return self


class BoardInput(BaseModel):
    provider: Literal["greenhouse", "lever", "ashby"]
    slug: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    employer: str = Field(min_length=1, max_length=200)


class Assessment(BaseModel):
    skills: float = Field(ge=0, le=100)
    experience: float = Field(ge=0, le=100)
    relevance: float = Field(ge=0, le=100)
    compensation: float = Field(ge=0, le=100)
    location: float = Field(ge=0, le=100)
    hard_requirements: Literal["pass", "fail", "unknown"]
    disqualifiers: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1, max_length=6000)

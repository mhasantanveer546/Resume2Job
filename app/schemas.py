"""Validated contracts at the API and generation boundaries."""
from typing import Annotated, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
Short = Annotated[str, Field(max_length=500)]
Lines = Annotated[list[Short], Field(max_length=100)]
class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra='ignore', allow_inf_nan=False)
    skills: Lines = Field(default_factory=list)
    education: Lines = Field(default_factory=list)
    experience: Lines = Field(default_factory=list)
    projects: Lines = Field(default_factory=list)
    certifications: Lines = Field(default_factory=list)
    achievements: Lines = Field(default_factory=list)
    years_experience: float = Field(default=0, ge=0, le=60)
    seniority: Literal['entry','junior','mid','senior','unknown'] = 'unknown'
    @field_validator('skills','education','experience','projects','certifications','achievements')
    @classmethod
    def unique(cls, v): return list(dict.fromkeys(x.strip() for x in v if x.strip()))
class JobPreferences(BaseModel):
    role: str = Field(default='', max_length=150)
    location: str = Field(default='', max_length=150)
    work_mode: Literal['','remote','hybrid','on-site'] = ''
    level: Literal['','entry','junior','mid','senior'] = ''
    job_type: Literal['','full-time','part-time','internship','contract'] = ''
    extra_skills: Lines = Field(default_factory=list)
    include_stretch: bool = False
class TextResume(BaseModel):
    text: str = Field(min_length=50, max_length=20000)
class AnalysisRequest(BaseModel):
    resume_id: str
    job_id: int
class ImpliedSkill(BaseModel):
    skill: str = Field(max_length=100)
    evidence: str = Field(min_length=10, max_length=500)
class AdvisorFinal(BaseModel):
    recommendation_ids: list[str] = Field(max_length=6)
class AgentActivity(BaseModel):
    step: str
    ms: int = 0
    detail: str = ''
class Job(BaseModel):
    id: int
    title: str
    company: str
    location: str
    mode: str
    type: str
    min_years: float = Field(ge=0)
    required: list[str]
    preferred: list[str]
    description: str
    source: str
    source_url: str = ''
    education: str = ''
    seniority: str = 'unknown'
class JobMatch(BaseModel):
    job_id: int
    score: float = Field(ge=0,le=100)
    breakdown: dict[str,float]
    matched: list[str]
    missing: list[str]
class Recommendation(BaseModel):
    id: str
    category: str
    action: str
    evidence: str
class GapReport(BaseModel):
    matching: list[str]
    missing: list[str]
    preferred_matching: list[str]
    preferred_missing: list[str]
    partial: list[dict]
    implied: list[ImpliedSkill] = Field(default_factory=list)
class KeywordReport(BaseModel):
    coverage: float = Field(ge=0,le=100)
    keywords: list[dict]
    note: str
class Analysis(BaseModel):
    skills: GapReport
    keywords: KeywordReport
    experience: dict
    recommendations: dict
    steps: list[AgentActivity]

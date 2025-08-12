from pydantic import BaseModel
from typing import List, Optional

class BaseKPI(BaseModel):
    metric_name: str
    value: str
    unit: str
    qualifiers: List[str] = []

class StandardKPI(BaseKPI):
    period_text: str
    metric_type: str

class CustomKPI(BaseKPI):
    description: str

class ExtractedKPIs(BaseModel):
    standard_kpis: List[StandardKPI]
    custom_kpis: List[CustomKPI]
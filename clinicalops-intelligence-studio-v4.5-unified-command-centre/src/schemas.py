from typing import List, Literal
from pydantic import BaseModel, Field

class ClinicalResult(BaseModel):
    test: str = ""
    finding: str = ""
    status: Literal["normal", "abnormal", "unknown"] = "unknown"

class ExtractionOutput(BaseModel):
    clinical_context: str = ""
    symptoms: List[str] = Field(default_factory=list)
    clinical_question: str = ""
    ordered_tests: List[str] = Field(default_factory=list)
    received_results: List[ClinicalResult] = Field(default_factory=list)
    missing_results: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    open_loop: bool = False
    priority: str = "routine review"
    missing_information: List[str] = Field(default_factory=list)
    model_notes: str = ""

class RuleTrigger(BaseModel):
    rule_id: str
    name: str
    flag: str
    priority: str
    evidence: str

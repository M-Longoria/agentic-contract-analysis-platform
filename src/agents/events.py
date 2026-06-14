from llama_index.core.workflow import Event
from typing import List, Optional


class FileParsingEvent(Event):
    vendor_id: str
    vendor_name: str
    vendor_data: dict


class ComplianceReviewEvent(Event):
    document_id: str
    agent_run_id: str
    parsed_text: str
    vendor_data: dict


class LegalReviewEvent(Event):
    vendor_id: str
    findings: List[str]
    risk_level: str
    citations: List[str]


class SecurityReviewEvent(Event):
    vendor_id: str
    findings: List[str]
    risk_level: str
    citations: List[str]


class SummaryEvent(Event):
    vendor_id: str
    legal_findings: dict
    security_findings: dict
    compiled_summary: str


class QAValidationEvent(Event):
    vendor_id: str
    summary: str
    is_valid: bool
    missing_citations: Optional[List[str]] = None
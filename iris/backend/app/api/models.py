from pydantic import BaseModel
from typing import List, Dict, Any

class UploadPDFResponse(BaseModel):
    paper_id: str
    filename: str

class AnalyzeRequest(BaseModel):
    session_id: str
    paper_id: str

class SynthesizeRequest(BaseModel):
    session_id: str
    paper_ids: List[str]

class EvaluationResponse(BaseModel):
    report: Dict[str, Any]

class FetchArxivRequest(BaseModel):
        session_id: str
        arxiv_id: str

class SuggestPapersRequest(BaseModel):
        session_id: str

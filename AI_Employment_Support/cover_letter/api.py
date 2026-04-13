from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import json

from database import get_db
import models
import crud

from cover_letter.service import generate_validated_cover_letter_versions

router = APIRouter()


class CoverLetterRequest(BaseModel):
    job_id: int
    resume_json: dict


@router.post("/generate")
async def generate_cover_letter_api(
    payload: CoverLetterRequest,
    db: Session = Depends(get_db)
):
    job = db.query(models.Enter).filter(models.Enter.id == payload.job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")

    # 기업 분석 가져오기 (있으면 활용)
    analysis = crud.get_company_analysis(db, payload.job_id)

    analysis_data = {}
    if analysis and analysis.analysis_report:
        if isinstance(analysis.analysis_report, str):
            try:
                analysis_data = json.loads(analysis.analysis_report)
            except Exception:
                analysis_data = {}
        elif isinstance(analysis.analysis_report, dict):
            analysis_data = analysis.analysis_report

    result = await generate_validated_cover_letter_versions(
        resume_json=payload.resume_json,
        enter_job=job,
        company_analysis=analysis_data,
    )

    return result
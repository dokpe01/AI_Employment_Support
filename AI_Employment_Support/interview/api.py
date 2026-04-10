import json
import asyncio
from typing import Optional, List


from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models

from .session import (
    create_session,
    get_session,
    get_current_question,
    save_answer,
    move_to_next_question,
)
from .service import generate_interview_questions
from .feedback import generate_final_feedback

router = APIRouter()

BAD_ANSWERS = {
    "모르겠습니다",
    "잘 모르겠습니다",
    "모르겠어요",
    "없습니다",
    "패스",
    "기억이 안 납니다",
    "기억 안 납니다",
    "잘 기억이 안 납니다",
    "음",
    "음...",
    "네",
    "아니요",
    "딱히 없습니다",
}


def is_insufficient_answer(answer: str) -> bool:
    text = answer.strip()

    if len(text) < 15:
        return True

    if text in BAD_ANSWERS:
        return True

    lowered = text.replace(" ", "")
    vague_patterns = ["모르겠", "없습니", "패스", "기억안", "잘모르"]
    if any(pattern in lowered for pattern in vague_patterns):
        return True

    return False


def build_retry_message(current_question: str) -> str:
    return (
        f"방금 질문은 '{current_question}'였습니다. "
        "답변이 조금 짧거나 구체성이 부족합니다. "
        "당시 상황, 본인의 역할, 실제 행동, 결과를 중심으로 한 번 더 말씀해주시겠어요?"
    )

class InterviewStartRequest(BaseModel):
    job_id: int
    resume: str

class InterviewStartResponse(BaseModel):
    session_id: str
    message: str
    question_index: int
    is_finished: bool


class InterviewAnswerRequest(BaseModel):
    message: str


class InterviewAnswerResponse(BaseModel):
    message: str
    question_index: int
    is_finished: bool


class InterviewFeedbackResponse(BaseModel):
    overall_summary: str
    strengths: List[str]
    weaknesses: List[str]
    improvements: List[str]
    sample_answer_tip: str


@router.post("/start")
async def start_interview(
    req: InterviewStartRequest,
    db: Session = Depends(get_db)
):
    print("DEBUG req:", req)

    job = db.query(models.Enter).filter(models.Enter.id == req.job_id).first()
    print("DEBUG job:", job)

    if not job:
        raise HTTPException(status_code=404, detail="선택한 공고를 찾을 수 없습니다.")

    job_text = f"""
회사명: {getattr(job, 'name', '')}
직무: {getattr(job, 'job', '')}
주요업무: {getattr(job, 'work', '')}
자격요건: {getattr(job, 'qual', '')}
우대사항: {getattr(job, 'prefer', '')}
채용절차: {getattr(job, 'procedure', '')}
"""
    print("DEBUG job_text:", job_text)

    questions = await generate_interview_questions(
        job_posting=job_text,
        resume=req.resume,
        company=getattr(job, 'name', ''),
        role=getattr(job, 'job', '')
    )
    print("DEBUG questions:", questions)

    session_id = create_session(
        company=getattr(job, 'name', ''),
        role=getattr(job, 'job', ''),
        job_posting=job_text,
        resume=req.resume,
        questions=questions
    )

    first_question = get_current_question(session_id)
    print("DEBUG first_question:", first_question)

    return {
        "session_id": session_id,
        "message": first_question,
        "question_index": 1,
        "is_finished": False
    }


@router.post("/{session_id}/answer", response_model=InterviewAnswerResponse)
async def answer_interview(session_id: str, req: InterviewAnswerRequest):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    if session["status"] == "finished":
        return InterviewAnswerResponse(
            message="면접이 이미 종료되었습니다. 종합 피드백을 확인해주세요.",
            question_index=session["question_index"],
            is_finished=True,
        )

    if not req.message.strip():
        raise HTTPException(status_code=400, detail="답변이 비어 있습니다.")

    current_question = get_current_question(session_id)

    # 1차 답변이 부실하면 1회 재질문
    if is_insufficient_answer(req.message) and session.get("retry_count", 0) < 1:
        session["retry_count"] = session.get("retry_count", 0) + 1

        return InterviewAnswerResponse(
            message=build_retry_message(current_question or "현재 질문"),
            question_index=session["question_index"] + 1,
            is_finished=False,
        )

    # 재질문 이후에도 부실하면 저장은 하되 다음으로 진행
    was_retried = session.get("retry_count", 0) > 0
    save_answer(session_id, req.message, was_retried=was_retried)
    session["retry_count"] = 0

    finished = move_to_next_question(session_id)

    if finished:
        return InterviewAnswerResponse(
            message="면접은 여기까지입니다. 종합 피드백을 받아보세요.",
            question_index=session["question_index"],
            is_finished=True,
        )

    next_question = get_current_question(session_id)

    return InterviewAnswerResponse(
        message=next_question,
        question_index=session["question_index"] + 1,
        is_finished=False,
    )


@router.post("/{session_id}/answer/stream")
async def answer_interview_stream(session_id: str, req: InterviewAnswerRequest):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    if not req.message.strip():
        raise HTTPException(status_code=400, detail="답변이 비어 있습니다.")

    if session["status"] == "finished":
        async def done_generator():
            yield json.dumps({
                "type": "done",
                "message": "면접이 이미 종료되었습니다. 종합 피드백을 확인해주세요.",
                "is_finished": True
            }, ensure_ascii=False) + "\n"

        return StreamingResponse(
            done_generator(),
            media_type="application/x-ndjson"
        )

    current_question = get_current_question(session_id)

    # 답변이 부족하면 재질문 1회
    if is_insufficient_answer(req.message) and session.get("retry_count", 0) < 1:
        session["retry_count"] = session.get("retry_count", 0) + 1
        retry_message = build_retry_message(current_question or "현재 질문")

        async def retry_generator():
            for token in retry_message.split():
                yield json.dumps({
                    "type": "chunk",
                    "content": token + " "
                }, ensure_ascii=False) + "\n"
                await asyncio.sleep(0.03)

            yield json.dumps({
                "type": "done",
                "is_finished": False,
                "question_index": session["question_index"] + 1,
                "is_retry": True
            }, ensure_ascii=False) + "\n"

        return StreamingResponse(retry_generator(), media_type="application/x-ndjson")

    was_retried = session.get("retry_count", 0) > 0
    save_answer(session_id, req.message, was_retried=was_retried)
    session["retry_count"] = 0
    finished = move_to_next_question(session_id)

    async def generator():
        if finished:
            final_message = "면접은 여기까지입니다. 종합 피드백을 받아보세요."
            for token in final_message.split():
                yield json.dumps({
                    "type": "chunk",
                    "content": token + " "
                }, ensure_ascii=False) + "\n"
                await asyncio.sleep(0.03)

            yield json.dumps({
                "type": "done",
                "is_finished": True
            }, ensure_ascii=False) + "\n"
            return

        next_question = get_current_question(session_id)

        for token in next_question.split():
            yield json.dumps({
                "type": "chunk",
                "content": token + " "
            }, ensure_ascii=False) + "\n"
            await asyncio.sleep(0.03)

        yield json.dumps({
            "type": "done",
            "is_finished": False,
            "question_index": session["question_index"] + 1
        }, ensure_ascii=False) + "\n"

    return StreamingResponse(generator(), media_type="application/x-ndjson")

@router.post("/{session_id}/finish")
async def finish_interview(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    if not session["history"]:
        raise HTTPException(status_code=400, detail="면접 기록이 없습니다.")

    feedback = await generate_final_feedback(
        company=session["company"],
        role=session["role"],
        job_posting=session["job_posting"],
        resume=session["resume"],
        history=session["history"],
    )
    print("DEBUG finish history:", session["history"])
    return feedback
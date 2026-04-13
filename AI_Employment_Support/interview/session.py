import uuid
from typing import Dict, Any, Optional

SESSION_STORE: Dict[str, Dict[str, Any]] = {}


def create_session(
    company: Optional[str],
    role: Optional[str],
    job_posting: str,
    resume: str,
    questions: list[str],
) -> str:
    session_id = str(uuid.uuid4())

    SESSION_STORE[session_id] = {
        "session_id": session_id,
        "company": company,
        "role": role,
        "job_posting": job_posting,
        "resume": resume,
        "questions": questions,
        "question_index": 0,
        "history": [],
        "status": "in_progress",
        "retry_count": 0,
    }
    return session_id


def get_session(session_id: str) -> Optional[dict]:
    return SESSION_STORE.get(session_id)


def get_current_question(session_id: str) -> Optional[str]:
    session = SESSION_STORE.get(session_id)
    if not session:
        return None

    idx = session["question_index"]
    questions = session["questions"]

    if idx >= len(questions):
        return None

    return questions[idx]


def save_answer(session_id: str, answer: str, was_retried: bool = False) -> None:
    session = SESSION_STORE[session_id]
    idx = session["question_index"]
    question = session["questions"][idx]

    session["history"].append({
        "question": question,
        "answer": answer.strip(),
        "was_retried": was_retried,
    })


def move_to_next_question(session_id: str) -> bool:
    session = SESSION_STORE[session_id]
    session["question_index"] += 1

    if session["question_index"] >= len(session["questions"]):
        session["status"] = "finished"
        return True

    return False
import os
import json
import faiss
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_NAME = "intfloat/multilingual-e5-base"
KEYWORD_PATH = os.path.join(CURRENT_DIR, "keywords.json")

def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        return [value]
    return [str(value).strip()]


def ensure_text(value, default="미기재"):
    if value is None:
        return default
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
        return ", ".join(items) if items else default
    value = str(value).strip()
    return value if value else default


def load_keywords():
    with open(KEYWORD_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_keywords_by_roles(desired_roles, keyword_dict):
    keywords = []

    for role in desired_roles:
        if role in keyword_dict:
            keywords.extend(keyword_dict[role])

    # 중복 제거
    return list(dict.fromkeys(keywords))


def get_all_keywords(keyword_dict):
    keywords = []
    for values in keyword_dict.values():
        keywords.extend(values)
    return list(dict.fromkeys(keywords))


def make_user_profile_text(resume_json: dict) -> str:
    name = ensure_text(resume_json.get("name"))
    desired_role = ensure_text(resume_json.get("desired_role"))
    skills = ensure_text(resume_json.get("skills"))
    certifications = ensure_text(resume_json.get("certifications"))
    awards = ensure_text(resume_json.get("awards"))
    languages = ensure_text(resume_json.get("languages"))

    exp_lines = []
    for exp in resume_json.get("experiences", []):
        exp_lines.append(
            "\n".join([
                f"회사: {ensure_text(exp.get('company'))}",
                f"역할: {ensure_text(exp.get('role'))}",
                f"기간: {ensure_text(exp.get('period'))}",
                f"주요업무: {ensure_text(exp.get('tasks'))}",
                f"성과: {ensure_text(exp.get('achievements'))}",
            ])
        )

    project_lines = []
    for proj in resume_json.get("projects", []):
        project_lines.append(
            "\n".join([
                f"프로젝트명: {ensure_text(proj.get('name'))}",
                f"기간: {ensure_text(proj.get('period'))}",
                f"설명: {ensure_text(proj.get('description'))}",
                f"기술: {ensure_text(proj.get('skills'))}",
            ])
        )

    education_lines = []
    for edu in resume_json.get("education", []):
        education_lines.append(
            "\n".join([
                f"학교: {ensure_text(edu.get('school'))}",
                f"전공: {ensure_text(edu.get('major'))}",
                f"학위: {ensure_text(edu.get('degree'))}",
            ])
        )

    parts = [
        f"이름: {name}",
        f"희망직무: {desired_role}",
        f"보유기술: {skills}",
        "[경력]",
        "\n\n".join(exp_lines) if exp_lines else "미기재",
        "[프로젝트]",
        "\n\n".join(project_lines) if project_lines else "미기재",
        "[학력]",
        "\n\n".join(education_lines) if education_lines else "미기재",
        f"자격증: {certifications}",
        f"수상: {awards}",
        f"언어: {languages}",
    ]

    return "\n".join(parts)


def rerank_score(user_profile: dict, job_item: dict, vector_score: float, keywords: list) -> float:
    bonus = 0.0

    user_text = (
        ensure_text(user_profile.get("desired_role"), "") + " " +
        ensure_text(user_profile.get("skills"), "") + " " +
        ensure_text([exp.get("role", "") for exp in user_profile.get("experiences", [])], "")
    ).lower()

    job_text = (
        ensure_text(job_item.get("job"), "") + " " +
        ensure_text(job_item.get("summary_text"), "") + " " +
        ensure_text(job_item.get("document_text"), "")
    ).lower()

    # 기술 스택 겹침 보정
    user_skills = [s.lower() for s in ensure_list(user_profile.get("skills"))]
    overlap = sum(1 for s in user_skills if s in job_text)
    bonus += min(overlap * 0.02, 0.12)

    # 선택 직무 기반 키워드 보정
    keyword_overlap = sum(
        1 for k in keywords
        if k.lower() in user_text and k.lower() in job_text
    )
    bonus += min(keyword_overlap * 0.015, 0.08)

    return vector_score + bonus


def match_jobs_for_resume(
    resume_json_path=None,
    index_path=None,
    meta_path=None,
    output_path=None,
    top_k=5
):
    resume_json_path = resume_json_path or os.path.join(DATA_DIR, "resume.json")
    index_path = index_path or os.path.join(DATA_DIR, "jobs_faiss.index")
    meta_path = meta_path or os.path.join(DATA_DIR, "jobs_metadata.json")
    output_path = output_path or os.path.join(DATA_DIR, "match_result.json")

    with open(resume_json_path, "r", encoding="utf-8") as f:
        resume_json = json.load(f)

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    keyword_dict = load_keywords()
    desired_roles = ensure_list(resume_json.get("desired_role"))
    selected_keywords = get_keywords_by_roles(desired_roles, keyword_dict)

    # 희망 직무가 비어 있으면 전체 키워드 fallback
    if not selected_keywords:
        selected_keywords = get_all_keywords(keyword_dict)

    model = SentenceTransformer(MODEL_NAME)
    index = faiss.read_index(index_path)

    user_text = make_user_profile_text(resume_json)

    query_vec = model.encode(
        [f"query: {user_text}"],
        normalize_embeddings=True,
        convert_to_numpy=True
    ).astype("float32")

    scores, indices = index.search(query_vec, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue

        item = meta[str(idx)]
        final_score = rerank_score(
            resume_json,
            item,
            float(score),
            selected_keywords
        )

        results.append({
            "faiss_id": int(idx),
            "vector_score": float(score),
            "final_score": float(final_score),
            "company_name": item.get("company_name"),
            "job": item.get("job"),
            "location": item.get("location"),
            "career": item.get("career"),
            "summary_text": item.get("summary_text"),
            "url": item.get("url"),
        })

    results = sorted(results, key=lambda x: x["final_score"], reverse=True)

    result = {
        "user_profile_text": user_text,
        "desired_role": desired_roles,
        "selected_keywords": selected_keywords,
        "matches": results
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result

if __name__ == "__main__":
    result = match_jobs_for_resume(top_k=5)
    print("\nmatch_result.json 저장 완료")
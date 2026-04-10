import os
import re
import json
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


# ---------------------------
# 공통 유틸
# ---------------------------

def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v) and str(v).strip()]
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else []
    return [str(value).strip()]


def ensure_text(value, default=""):
    if value is None:
        return default
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v) and str(v).strip()]
        return ", ".join(items) if items else default
    value = str(value).strip()
    return value if value else default


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path: str):
    output_dir = os.path.dirname(path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_jobs_meta():
    """
    jobs_metadata.json / jobs_meta.json 둘 다 대응
    """
    candidate_paths = [
        os.path.join(DATA_DIR, "jobs_metadata.json"),
        os.path.join(DATA_DIR, "jobs_meta.json"),
    ]

    for path in candidate_paths:
        if os.path.exists(path):
            return load_json(path), path

    raise FileNotFoundError("jobs_metadata.json 또는 jobs_meta.json 파일을 찾을 수 없습니다.")


# ---------------------------
# 컨텍스트 구성
# ---------------------------

def build_user_fact_profile(resume_json: dict) -> dict:
    """
    자소서 생성에 사용할 사용자 사실 정보만 추림
    """
    return {
        "name": resume_json.get("name", ""),
        "email": resume_json.get("email", ""),
        "phone": resume_json.get("phone", ""),
        "links": resume_json.get("links", []),
        "skills": resume_json.get("skills", []),
        "experiences": resume_json.get("experiences", []),
        "projects": resume_json.get("projects", []),
        "education": resume_json.get("education", []),
        "certifications": resume_json.get("certifications", []),
        "awards": resume_json.get("awards", []),
        "languages": resume_json.get("languages", []),
        "desired_role": resume_json.get("desired_role", []),
    }


def normalize_job_meta(job_meta: dict) -> dict:
    """
    jobs_metadata.json 키 구조 차이를 흡수
    - company_name 없으면 name 사용
    - job_posting 없으면 metadata 사용
    """
    company_name = job_meta.get("company_name", "") or job_meta.get("name", "")
    job_posting = job_meta.get("job_posting", {})
    if not job_posting:
        job_posting = job_meta.get("metadata", {})

    return {
        "company_name": company_name,
        "job": job_meta.get("job", ""),
        "location": job_meta.get("location", ""),
        "career": job_meta.get("career", ""),
        "summary_text": job_meta.get("summary_text", ""),
        "job_posting": job_posting,
        "url": job_meta.get("url", ""),
        "source": job_meta.get("source", ""),
        "job_text": job_meta.get("job_text", ""),
        "document_text": job_meta.get("document_text", ""),
        "company_analysis": job_meta.get("company_analysis", {}),
    }


def build_cover_letter_context(resume_json: dict, selected_job: dict, jobs_meta: dict) -> dict:
    faiss_id = str(selected_job["faiss_id"])
    raw_job_meta = jobs_meta[faiss_id]
    job_meta = normalize_job_meta(raw_job_meta)

    return {
        "user_profile": build_user_fact_profile(resume_json),
        "job_posting": {
            "company_name": job_meta["company_name"],
            "job": job_meta["job"],
            "location": job_meta["location"],
            "career": job_meta["career"],
            "summary_text": job_meta["summary_text"],
            "job_posting": job_meta["job_posting"],
            "url": job_meta["url"],
            "source": job_meta["source"],
            "job_text": job_meta["job_text"],
            "document_text": job_meta["document_text"],
        },
        "company_analysis": job_meta["company_analysis"],
        "retrieval_info": {
            "vector_score": selected_job.get("vector_score"),
            "final_score": selected_job.get("final_score"),
        }
    }


# ---------------------------
# 프롬프트
# ---------------------------

def get_strategy_guide(strategy: str) -> str:
    strategy_map = {
        "balanced": """
- 지원동기, 직무 적합성, 협업 경험, 입사 후 포부를 균형 있게 작성하라.
- 특정 한 항목만 과도하게 강조하지 마라.
""".strip(),
        "job_fit_focus": """
- 직무 적합성과 기술/프로젝트/실무 경험을 더 강하게 강조하라.
- 채용공고의 주요업무, 자격요건, 우대사항과 사용자 경험을 최대한 직접적으로 연결하라.
- 지원동기보다 직무 적합성의 비중을 더 높게 작성하라.
""".strip(),
        "motivation_focus": """
- 지원동기와 문제의식, 회사/직무와의 연결성을 더 강조하라.
- 사용자가 왜 이 직무와 회사에 적합한지 서사적으로 설득하라.
- 직무 적합성도 포함하되 지원동기와 기여 의지의 비중을 더 높게 작성하라.
""".strip(),
    }
    return strategy_map.get(strategy, strategy_map["balanced"])


def make_cover_letter_prompt(context: dict, strategy: str = "balanced") -> str:
    strategy_guide = get_strategy_guide(strategy)

    return f"""
너는 채용 자기소개서 초안을 작성하는 도우미다.

반드시 아래 자료만 근거로 작성하라.

[절대 규칙]
1. 사용자 경험에 없는 내용은 절대 추가하지 마라.
2. 사용자 성과 수치가 없으면 임의 숫자를 만들지 마라.
3. 채용공고에 없는 기업 사실은 단정하지 마라.
4. company_analysis는 지원동기와 기업 이해 보강용 참고자료로만 사용하라.
5. job_posting의 주요업무, 자격요건, 우대사항을 기준으로 직무 적합성을 설명하라.
6. 자소서 문장을 새로 작성해야 하며, 기존 자기소개서 문장을 복원하거나 재사용하지 마라.
7. user_profile에는 사실 정보만 들어 있으며, 이것만 사용하라.
8. 과장된 표현보다 근거 중심으로 작성하라.
9. user_profile의 desired_role을 사용자의 희망 직무 정보로 간주하고, 채용공고의 직무와 어떻게 연결되는지 반영하라.
10. 출력은 반드시 JSON 형식으로 작성하라.

[문체 및 형식 규칙]
1. 편지 형식으로 쓰지 마라.
2. "안녕하세요", "감사합니다", "잘 부탁드립니다" 같은 인사말을 쓰지 마라.
3. 마지막에 이름, 서명, 날짜를 쓰지 마라.
4. GitHub 링크, URL, 이메일, 전화번호를 본문에 직접 쓰지 마라.
5. 결과는 4개의 문단으로 구성하되, 문단 제목은 쓰지 마라.
6. 마지막 문단은 반드시 입사 후 기여 포부 성격으로 작성하라.
7. 마지막 문장은 포부와 기여 의지가 드러나는 문장으로 마무리하라.
8. 본문만 작성하고, 머리말/맺음말/서명은 넣지 마라.
9. 각 문단은 3~5문장 이내로 작성하라.
10. 지원자의 강점이 공고 요구사항과 어떻게 연결되는지 드러나게 작성하라.
11. 사용자 링크 정보가 있더라도 본문에는 링크를 삽입하지 마라.

[작성 전략]
{strategy_guide}

[출력 스키마]
{{
  "company_name": "",
  "job": "",
  "support_motivation": "",
  "job_fit": "",
  "collaboration_problem_solving": "",
  "future_contribution": "",
  "evidence_mapping": [
    {{
      "job_requirement": "",
      "user_evidence": ""
    }}
  ]
}}

[문단별 작성 기준]
- support_motivation: 지원동기와 문제의식 중심
- job_fit: 직무 적합성과 기술/프로젝트/실무 경험 중심
- collaboration_problem_solving: 협업 태도와 문제 해결 경험 중심
- future_contribution: 입사 후 어떤 방식으로 기여할지 중심

[사용자 사실 정보]
{json.dumps(context["user_profile"], ensure_ascii=False, indent=2)}

[채용공고 정보]
{json.dumps(context["job_posting"], ensure_ascii=False, indent=2)}

[기업분석 정보]
{json.dumps(context["company_analysis"], ensure_ascii=False, indent=2)}
""".strip()


# ---------------------------
# 후처리
# ---------------------------

def postprocess_cover_letter(text: str, applicant_name: str = "") -> str:
    if not text:
        return ""

    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', text)
    text = re.sub(r'01[0-9]-?\d{3,4}-?\d{4}', '', text)

    text = re.sub(r'^\s*안녕하세요[^\n]*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*안녕하십니까[^\n]*\n?', '', text, flags=re.MULTILINE)

    ending_patterns = [
        r'\n?\s*감사합니다\.?\s*$',
        r'\n?\s*잘 부탁드립니다\.?\s*$',
        r'\n?\s*읽어주셔서 감사합니다\.?\s*$',
        r'\n?\s*이상입니다\.?\s*$',
    ]

    for pattern in ending_patterns:
        text = re.sub(pattern, '', text, flags=re.MULTILINE)

    if applicant_name:
        escaped_name = re.escape(applicant_name.strip())
        text = re.sub(rf'\n?\s*{escaped_name}\s*$', '', text, flags=re.MULTILINE)

    text = re.sub(
        r'^\s*(지원동기|직무 적합성|협업 및 문제 해결|입사 후 포부)[:：]?\s*',
        '',
        text,
        flags=re.MULTILINE
    )

    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def ensure_strong_ending(text: str) -> str:
    if not text:
        return ""

    good_endings = (
        "기여하겠습니다.",
        "성장하겠습니다.",
        "만들어가겠습니다.",
        "만들어내겠습니다.",
        "실현하겠습니다.",
        "돕겠습니다.",
        "보탬이 되겠습니다.",
    )

    if not text.endswith(good_endings):
        text += "\n\n이러한 경험을 바탕으로 서비스의 문제를 구조적으로 정의하고, 데이터와 시스템 흐름을 연결해 실질적인 개선을 만들어내는 데 기여하겠습니다."

    return text.strip()


def clean_section_text(text: str, applicant_name: str = "") -> str:
    return postprocess_cover_letter(text, applicant_name=applicant_name).strip()


def build_full_cover_letter_from_sections(result: dict, applicant_name: str = "") -> str:
    sections = [
        clean_section_text(result.get("support_motivation", ""), applicant_name),
        clean_section_text(result.get("job_fit", ""), applicant_name),
        clean_section_text(result.get("collaboration_problem_solving", ""), applicant_name),
        clean_section_text(result.get("future_contribution", ""), applicant_name),
    ]

    sections = [s for s in sections if s]
    full_text = "\n\n".join(sections)
    full_text = postprocess_cover_letter(full_text, applicant_name=applicant_name)
    full_text = ensure_strong_ending(full_text)
    return full_text


# ---------------------------
# LLM 생성
# ---------------------------

async def generate_cover_letter_draft(context: dict, strategy: str = "balanced") -> dict:
    prompt = make_cover_letter_prompt(context, strategy)

    response = await client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": "너는 사실 정보와 채용공고를 바탕으로 새로운 자기소개서 초안을 JSON으로 작성하는 도우미다."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        response_format={"type": "json_object"}
    )

    content = response.choices[0].message.content.strip()

    try:
        result = json.loads(content)
    except Exception:
        result = {
            "company_name": context["job_posting"].get("company_name", ""),
            "job": context["job_posting"].get("job", ""),
            "support_motivation": "",
            "job_fit": "",
            "collaboration_problem_solving": "",
            "future_contribution": "",
            "evidence_mapping": []
        }

    applicant_name = context["user_profile"].get("name", "").strip()

    result["support_motivation"] = clean_section_text(result.get("support_motivation", ""), applicant_name)
    result["job_fit"] = clean_section_text(result.get("job_fit", ""), applicant_name)
    result["collaboration_problem_solving"] = clean_section_text(result.get("collaboration_problem_solving", ""), applicant_name)
    result["future_contribution"] = clean_section_text(result.get("future_contribution", ""), applicant_name)
    result["full_cover_letter"] = build_full_cover_letter_from_sections(result, applicant_name)

    return result


# ---------------------------
# 서버용 함수
# ---------------------------

async def generate_cover_letters(
    resume_json: dict,
    match_result: dict,
    jobs_meta: dict
) -> dict:
    """
    서버에서 바로 호출할 수 있는 함수형 로직
    입력: resume_json, match_result, jobs_meta
    출력: cover_letter_draft 구조(dict)
    """
    if not match_result.get("matches"):
        raise ValueError("매칭 결과가 없습니다.")

    selected_job = match_result["matches"][0]

    context = build_cover_letter_context(
        resume_json=resume_json,
        selected_job=selected_job,
        jobs_meta=jobs_meta
    )

    strategies = [
        ("v1", "balanced"),
        ("v2", "job_fit_focus"),
        ("v3", "motivation_focus"),
    ]

    cover_letters = []

    for version, strategy in strategies:
        draft = await generate_cover_letter_draft(context, strategy)
        cover_letters.append({
            "version": version,
            "strategy": strategy,
            "draft": draft
        })

    return {
        "selected_job": selected_job,
        "job_source": {
            "source": context["job_posting"].get("source", ""),
            "url": context["job_posting"].get("url", ""),
            "job_posting_raw": context["job_posting"].get("job_posting", {}),
        },
        "context": context,
        "cover_letters": cover_letters
    }


async def generate_cover_letters_from_files(
    resume_json_path: str = None,
    match_result_path: str = None,
    output_path: str = None
) -> dict:
    """
    로컬 테스트용 파일 기반 실행 함수
    """
    resume_json_path = resume_json_path or os.path.join(DATA_DIR, "resume.json")
    match_result_path = match_result_path or os.path.join(DATA_DIR, "match_result.json")
    output_path = output_path or os.path.join(DATA_DIR, "cover_letter_draft.json")

    resume_json = load_json(resume_json_path)
    match_result = load_json(match_result_path)
    jobs_meta, _ = load_jobs_meta()

    result = await generate_cover_letters(resume_json, match_result, jobs_meta)
    save_json(result, output_path)
    return result


# ---------------------------
# 출력용
# ---------------------------

def print_cover_letter_preview(draft: dict, version: str = "", strategy: str = ""):
    print("\n" + "=" * 100)
    if version or strategy:
        print(f"[{version}] strategy={strategy}")
    print(f"회사명: {draft.get('company_name', '')}")
    print(f"직무: {draft.get('job', '')}")
    print("=" * 100)
    print("\n[자소서 본문]\n")
    print(draft.get("full_cover_letter", ""))
    print("\n" + "=" * 100)


# ---------------------------
# 테스트 실행용
# ---------------------------

async def main():
    result = await generate_cover_letters_from_files()
    print(f"자소서 초안 생성 완료: {os.path.join(DATA_DIR, 'cover_letter_draft.json')}")

    for item in result["cover_letters"]:
        print_cover_letter_preview(
            item["draft"],
            version=item["version"],
            strategy=item["strategy"]
        )


if __name__ == "__main__":
    asyncio.run(main())
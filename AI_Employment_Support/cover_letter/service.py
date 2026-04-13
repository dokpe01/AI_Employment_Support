import os
import re
import json
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI"))


# ---------------------------
# 1. 컨텍스트 구성
# ---------------------------

def build_user_fact_profile(resume_json: dict) -> dict:
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
        "target_jobs": resume_json.get("target_jobs", []),
    }


def build_cover_letter_context_from_db(
    resume_json: dict,
    enter_job: Any,
    company_analysis: dict | None = None,
) -> dict:
    return {
        "user_profile": build_user_fact_profile(resume_json),
        "job_posting": {
            "company_name": enter_job.name or "",
            "job": enter_job.job or "",
            "location": enter_job.location or "",
            "career": getattr(enter_job, "career", "") or "",
            "summary_text": "",
            "job_posting": {
                "work": enter_job.work or "",
                "qual": enter_job.qual or "",
                "prefer": enter_job.prefer or "",
                "procedure": enter_job.procedure or "",
                "docs": enter_job.docs or "",
            },
            "url": enter_job.url or "",
            "source": enter_job.source or "",
            "job_text": enter_job.content or "",
            "document_text": enter_job.content or "",
        },
        "company_analysis": company_analysis or {},
        "retrieval_info": {
            "vector_score": None,
            "final_score": None,
        },
    }


# ---------------------------
# 2. 프롬프트
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
9. 출력은 반드시 JSON 형식으로 작성하라.

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
# 3. 후처리 유틸
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

    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def clean_section_text(text: str, applicant_name: str = "") -> str:
    return postprocess_cover_letter(text, applicant_name=applicant_name).strip()


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
        text += "\n\n데이터 기반 문제 해결 역량을 바탕으로 서비스 개선에 실질적으로 기여하겠습니다."
    return text.strip()


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


def rule_based_clean(text: str, name: str = "") -> str:
    if not text:
        return ""

    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', text)
    text = re.sub(r'01[0-9]-?\d{3,4}-?\d{4}', '', text)
    text = re.sub(r'^\s*안녕하세요[^\n]*\n?', '', text)
    text = re.sub(r'^\s*안녕하십니까[^\n]*\n?', '', text)
    text = re.sub(r'(감사합니다\.?|잘 부탁드립니다\.?)$', '', text)

    if name:
        text = re.sub(rf'\n?\s*{re.escape(name)}\s*$', '', text)

    return text.strip()


# ---------------------------
# 4. 초안 생성
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
# 5. 검증
# ---------------------------

async def llm_validate_cover_letter(draft_text: str, context: dict) -> dict:
    prompt = f"""
다음 자기소개서를 검증하고 수정하세요.

[검증 기준]
1. 사용자 경험에 없는 내용이 있는가?
2. 성과 수치가 근거 없이 추가되었는가?
3. 채용공고와 무관한 내용이 있는가?
4. 과장된 표현이 있는가?
5. 자소서 문체가 자연스러운가?

[수정 규칙]
- 잘못된 내용은 제거 또는 수정
- 없는 정보는 추가하지 말 것
- 자연스럽게 다시 작성
- 반드시 JSON으로 출력

[출력 스키마]
{{
  "issues": [],
  "corrected_text": ""
}}

[사용자 정보]
{json.dumps(context["user_profile"], ensure_ascii=False)}

[자소서]
{draft_text}
"""

    response = await client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": "너는 자기소개서를 검증하는 전문가다."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )

    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {
            "issues": [],
            "corrected_text": draft_text,
        }


# ---------------------------
# 6. 최종 통합 함수
# ---------------------------

async def generate_validated_cover_letter_versions(
    resume_json: dict,
    enter_job: Any,
    company_analysis: dict | None = None,
) -> dict:
    context = build_cover_letter_context_from_db(
        resume_json=resume_json,
        enter_job=enter_job,
        company_analysis=company_analysis,
    )

    strategies = [
        ("v1", "balanced")
    ]

    validated_cover_letters = []
    applicant_name = context["user_profile"].get("name", "").strip()

    for version, strategy in strategies:
        draft = await generate_cover_letter_draft(context, strategy)

        raw_text = draft.get("full_cover_letter", "")
        cleaned = rule_based_clean(raw_text, applicant_name)

        final_text = ensure_strong_ending(cleaned)
        validated = {"issues": []}

        validated_cover_letters.append({
            "version": version,
            "strategy": strategy,
            "draft": draft,
            "original": raw_text,
            "cleaned": cleaned,
            "issues": [],
            "final": final_text,
        })

    return {
        "context": context,
        "validated_cover_letters": validated_cover_letters,
    }
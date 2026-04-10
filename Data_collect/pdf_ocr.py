import os
import fitz
import pytesseract
from PIL import Image, ImageOps
import asyncio
import json
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def ocr_page(page, zoom=4):
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    # OCR 품질 개선용 간단 전처리
    img = ImageOps.grayscale(img)
    img = img.point(lambda x: 0 if x < 180 else 255, mode='1')

    text = pytesseract.image_to_string(img, lang='kor+eng')
    return text


def extract_text_pdf(pdf_path, min_text_length=30):
    full_content = []

    try:
        with fitz.open(pdf_path) as doc:
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                text = page.get_text("text").strip()

                # 텍스트가 충분히 있으면 그대로 사용
                if len(text) >= min_text_length:
                    full_content.append(f"[PAGE {page_idx + 1}]\n{text}")
                else:
                    ocr_text = ocr_page(page).strip()
                    full_content.append(f"[PAGE {page_idx + 1}]\n{ocr_text}")

    except Exception as e:
        print(f"PDF 처리 실패: {e}")
        return ""

    return "\n\n".join(full_content)


def save_to_txt(content, output_path):
    try:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

    except Exception as e:
        print(f"저장 실패: {e}")

def save_to_json(data, output_path):
    try:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"JSON 저장 실패: {e}")

async def llm_resume_to_json(resume_text: str) -> dict:
    prompt = f"""
다음 이력서 텍스트를 분석하여 JSON 형식으로 구조화하세요.

[중요]
이 문서에는 자기소개서 문장이나 지원동기/입사 후 포부가 포함될 수도 있고, 없을 수도 있습니다.
- 포함되어 있다면 해당 문장들은 excluded_self_intro_text에만 저장하세요.
- 포함되어 있지 않다면 excluded_self_intro_text는 빈 리스트([])로 두세요.
- experiences, projects, skills, education 등에는 사실 정보만 넣으세요.
- 자소서성 문장을 사실 정보로 섞지 마세요.

[자소서성 문장 예시]
- 지원동기
- 입사 후 포부
- 회사에 기여하고 싶다는 문장
- 자기 PR 중심의 자소서형 문단
- 편지형 인사말/맺음말
- "안녕하세요", "감사합니다", "기여하겠습니다", "성장하겠습니다" 등으로 끝나는 문장

[사실 정보 예시]
- 이름, 이메일, 전화번호, 링크
- 회사명, 역할, 기간
- 수행 업무
- 프로젝트 설명
- 사용 기술
- 자격증, 학력, 수상, 언어
- 객관적 성과
- 희망 직무(명시된 경우만)

[규칙]
1. 반드시 JSON만 출력하세요.
2. 없는 정보는 "" 또는 []로 채우세요.
3. 추측하지 마세요.
4. 날짜/기간은 가능한 한 원문 그대로 유지하세요.
5. tasks, achievements, skills는 리스트로 작성하세요.
6. raw_text에는 원문 전체를 넣으세요.
7. has_self_intro_text는 excluded_self_intro_text가 비어있지 않으면 true, 비어있으면 false로 설정하세요.

[스키마]
{{
  "name": "",
  "email": "",
  "phone": "",
  "links": [],
  "skills": [],
  "experiences": [
    {{
      "company": "",
      "role": "",
      "period": "",
      "tasks": [],
      "achievements": []
    }}
  ],
  "projects": [
    {{
      "name": "",
      "period": "",
      "description": "",
      "skills": [],
      "achievements": []
    }}
  ],
  "education": [
    {{
      "school": "",
      "major": "",
      "degree": ""
    }}
  ],
  "certifications": [],
  "awards": [],
  "languages": [],
  "target_jobs": [],
  "raw_text": "",
  "has_self_intro_text": false,
  "excluded_self_intro_text": []
}}

[이력서 텍스트]
{resume_text}
""".strip()

    response = await client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": "너는 이력서에서 사실 정보와 자기소개서성 문장을 구분하여 JSON으로 구조화하는 파서다."
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
            "name": "",
            "email": "",
            "phone": "",
            "links": [],
            "skills": [],
            "experiences": [],
            "projects": [],
            "education": [],
            "certifications": [],
            "awards": [],
            "languages": [],
            "target_jobs": [],
            "raw_text": resume_text,
            "has_self_intro_text": False,
            "excluded_self_intro_text": []
        }

    # 방어 코드
    result.setdefault("name", "")
    result.setdefault("email", "")
    result.setdefault("phone", "")
    result.setdefault("links", [])
    result.setdefault("skills", [])
    result.setdefault("experiences", [])
    result.setdefault("projects", [])
    result.setdefault("education", [])
    result.setdefault("certifications", [])
    result.setdefault("awards", [])
    result.setdefault("languages", [])
    result.setdefault("target_jobs", [])
    result.setdefault("raw_text", resume_text)
    result.setdefault("has_self_intro_text", False)
    result.setdefault("excluded_self_intro_text", [])

    # 타입 보정
    list_fields = [
        "links", "skills", "experiences", "projects", "education",
        "certifications", "awards", "languages", "target_jobs",
        "excluded_self_intro_text"
    ]
    for field in list_fields:
        if not isinstance(result.get(field), list):
            value = result.get(field)
            result[field] = [value] if value not in [None, ""] else []

    if not isinstance(result.get("has_self_intro_text"), bool):
        result["has_self_intro_text"] = len(result.get("excluded_self_intro_text", [])) > 0

    return result

async def main():
    pdf_path = "./data/resume.pdf"
    txt_output_path = pdf_path.replace(".pdf", ".txt")
    json_output_path = pdf_path.replace(".pdf", ".json")

    raw_text = extract_text_pdf(pdf_path)

    if not raw_text.strip():
        print("추출된 텍스트가 없습니다.")
        return

    # 디버깅용 txt 저장
    save_to_txt(raw_text, txt_output_path)

    # JSON 구조화
    resume_json = await llm_resume_to_json(raw_text)
    save_to_json(resume_json, json_output_path)

    print("이력서 JSON 변환 완료")
    print(f"has_self_intro_text: {resume_json.get('has_self_intro_text')}")
    print(f"excluded_self_intro_text 개수: {len(resume_json.get('excluded_self_intro_text', []))}")


if __name__ == "__main__":
    asyncio.run(main())

import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_to_schema(content):
    """JD 본문을 나영님의 DB 스키마 형식으로 변환"""
    prompt = f"""
    아래 채용 공고 본문에서 정보를 추출하여 JSON 형식으로 출력하세요.
    
    [스키마]
    - name: 기업명
    - period: 모집기간 (YYYY-MM-DD, 상시채용은 '상시채용')
    - job: 직무, 직무개요
    - location: 근무지,근무지역,회사위치(도로명주소형태)
    - work: 주요업무,담당업무, 이런 업무(리스트 형태 텍스트)
    - qual: 자격요건 (리스트 형태 텍스트)
    - prefer: 우대사항 (리스트 형태 텍스트)
    - procedure: 채용절차
    - docs: 제출서류(필요한 서류명을 가지고 오세요)
    - apply: 접수방법 

    [공고 본문]
    {content}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini", # 테스트용으로는 가성비 좋은 mini 모델 추천!
        messages=[
            {"role": "system", "content": "스키마 내용을 json content 내용에서 스키마 조건에 충족하도록 모두 찾아 채워주세요, content 내용에 없다면 미기재라고 채워주세요"},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0
    )
    return json.loads(response.choices[0].message.content)

# --- 메인 실행 로직 ---
file_path = "./data/ocr_data.json"

try:
    with open(file_path, "r", encoding="utf-8") as f:
        job_data = json.load(f)

  
    test_targets = job_data
    print(f"🚀 총 {len(job_data)}건 중 상위 5건에 대해 테스트 가공을 시작합니다.")

    final_results = []
    for i, job in enumerate(test_targets):
        content = job.get('content', '')
        crawled_location = job.get('location', '미확인')

        if content:
            print(f"🔄 [{i+1}/5] '{job.get('title')}' 분석 중...")
            try:
                # LLM 가공 호출
                structured = extract_to_schema(content)
                llm_location = structured.get('location', '').strip()
                if not llm_location or llm_location == "미기재":
                    # 크롤링 데이터가 '미확인'이 아닐 때만 덮어쓰기
                    if crawled_location != "미확인":
                        structured['location'] = crawled_location
                # 기존 데이터(url 등)와 가공 데이터를 합치면 더 완벽해요!
                structured['url'] = job.get('url')
                structured['source'] = job.get('source')
                if structured['name'] == '미기재':
                    structured['name'] = job.get('company')
                final_results.append(structured)
            except Exception as e:
                print(f"⚠️ 에러 발생 ({job.get('title')}): {e}")
        else:
            print(f"⏩ [{i+1}/5] 본문이 없어 건너뜁니다.")

    # 3. 테스트 결과 저장
    with open("LLMtest_f.json", "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=4)
    
    print(f"\n✅ 테스트 완료! 'LLMtest.json' 파일을 확인해 보세요.")

except FileNotFoundError:
    print("❌ 파일을 찾을 수 없습니다.")
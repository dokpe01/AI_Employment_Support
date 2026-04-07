import json
import os
import asyncio  # 비동기 처리
from openai import AsyncOpenAI  
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def llm_to_schema(content, semaphore):
    """JD 본문을 DB 스키마 형식으로 변환"""

    async with semaphore:
        prompt = f"""
        아래 채용 공고 본문에서 정보를 추출하여 JSON 형식으로 출력하세요.
        
        [스키마]
        - name: 기업명
        - period: 모집기간 (YYYY-MM-DD, 상시채용은 '상시채용')
        - job: 모집부분,직무, 직무개요, 역할
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

        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "스키마 내용을 json content 내용에서 스키마 조건에 충족하도록 모두 찾아 채워주세요, content 내용에 없다면 미기재라고 채워주세요"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": str(e)}

async def process_job(i, job, semaphore):
    content = job.get('content', '')
    crawled_location = job.get('location', '')
    crawled_period = job.get('period', '')
    
    if not content:
        print(f"⏩ [{i+1}] 본문이 없어 건너뜁니다.")
        return None

    try:
        # LLM 가공
        structured = await llm_to_schema(content, semaphore)

        if "error" in structured:
            print(f"⚠️ 에러 발생 ({job.get('title')}): {structured['error']}")
            return None

        if structured.get('location') in ["", "미기재", None]:
            if crawled_location:
                structured['location'] = crawled_location
        if structured.get('period') in ["", "미기재", None]:
            if crawled_period:
                structured['period'] = crawled_period
        if structured.get('name') in ["", "미기재", None]:
            if job.get('company'):
                structured['name'] = job.get('company')


        structured['url'] = job.get('url')
        structured['source'] = job.get('source')
        structured['collected_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if structured.get('name') == '미기재':
            structured['name'] = job.get('company')
            
        print(f"✅ [{i+1}] 가공 완료: {job.get('title')}")
        return structured

    except Exception as e:
        print(f"⚠️ 시스템 에러 ({job.get('title')}): {e}")
        return None

async def main():
    file_path = "./data/ocr_data.json"
    output_path = "./data/LLM_data.json"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            targets = json.load(f)

        print(f"🚀 총 {len(targets)}건 비동기 가공 시작 (병렬 처리)")

        # 동시 요청 
        semaphore = asyncio.Semaphore(10)

        tasks = [process_job(i, job, semaphore) for i, job in enumerate(targets)]
        results = await asyncio.gather(*tasks)
        final_results = [r for r in results if r is not None]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_results, f, ensure_ascii=False, indent=4)
        
        print(f"\n✅ 가공 완료! 총 {len(final_results)}건이 저장되었습니다.")

    except FileNotFoundError:
        print("❌ 파일을 찾을 수 없습니다.")

if __name__ == "__main__":
    asyncio.run(main())
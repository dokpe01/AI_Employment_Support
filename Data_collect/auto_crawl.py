import sys
import os
import json
import time
import asyncio
from datetime import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))

from dotenv import load_dotenv
from sqlalchemy import text

from data_crawling import run_parallel_scraping
from duplicate import process_deduplication
from data_ocr import run_detail_process
import LLM as LLM
from async_database import AsyncSessionLocal
from async_models import Enter

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

async def get_user_keywords(user_id):
    """DB에서 특정 사용자의 희망 직종을 가져옴"""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                text('SELECT job FROM "User" WHERE id = :id'),
                {"id": user_id}
            )
            row = result.first()
            if row and row[0]:
                return [k.strip() for k in row[0].split(',')]
        except Exception as e:
            print(f" DB 키워드 조회 중 에러: {e}")
        return None

def load_json_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
    
def to_text(value):
    if isinstance(value, list):
        return ", ".join(value)
    return value
    
async def insert_enter_data(data_list):
    async with AsyncSessionLocal() as session:
        try:
            for item in data_list:
                new_data = Enter(
                name=item.get("name", "정보없음"),
                period=item.get("period", "미정"),
                job=to_text(item.get("job")),
                location=to_text(item.get("location")),
                work=to_text(item.get("work")),
                qual=to_text(item.get("qual")),
                prefer=to_text(item.get("prefer")),
                procedure=to_text(item.get("procedure")),
                docs=to_text(item.get("docs")),
                apply=item.get("apply", "미기재"),
                url=item.get("url"),
                source=item.get("source", "unknown"),
                career=to_text(item.get("career")),
                collected_at=item.get("collected_at")
            )
                session.add(new_data)

            await session.commit()
            print(f"{len(data_list)}개 데이터 DB 저장 완료")

        except Exception as e:
            await session.rollback()
            print(f"DB 저장 중 에러: {e}")

async def run_total_automation(user_id):
    start_total = time.time()
    # 추후 사용자가 선택한 직무가 들어가도록 수정 예정
    keywords = await get_user_keywords(user_id)
    if not keywords:
        print(f"사용자(ID: {user_id})의 희망직종이 설정되지 않았습니다.")
        return 

    #각 사이트에서 링크 크롤링 
    raw_list = run_parallel_scraping(keywords, max_items_per_site=20)

    #DB에 있는 기존 데이터들은 제거 
    async with AsyncSessionLocal() as session:
        # DB의 모든 URL을 가져옴 (또는 최근 2주치만 가져와도 충분)
        result = await session.execute(text('SELECT url FROM "Enter"'))
        existing_urls = {row[0] for row in result.fetchall()}
    
    # DB에 없는 새로운 공고만 남김
    new_raw_list = [item for item in raw_list if item.get('url') not in existing_urls]
    
    if not new_raw_list:
        print("새로운 공고가 없습니다. 작업을 종료합니다.")
        return
    
    data_dir = os.path.join(current_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    raw_path = os.path.join(data_dir, "total_site_link_final.json")
    refined_path = os.path.join(data_dir, "refined_data.json")
    ocr_output_path = os.path.join(data_dir, "ocr_data.json")
    final_output_path = os.path.join(data_dir, "LLM_data.json")

    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(new_raw_list, f, ensure_ascii=False, indent=4)

    # 중복 공고 제거
    process_deduplication(raw_path, refined_path)

    #OCR
    run_detail_process(refined_path, ocr_output_path, workers=3)
    
    #LLM 가공 (비동기)
    await LLM.main()

    #DB저장
    print("LLM 파일 존재 여부:", os.path.exists(final_output_path))
    final_data = load_json_file(final_output_path)
    print("최종 데이터 개수:", len(final_data))
    print("샘플데이터:", final_data[:2])
    await insert_enter_data(final_data)

    end_total = time.time()
    print(f"\n 모든 자동화 공정 완료! (총 소요 시간: {round(end_total - start_total, 2)}초)")

if __name__ == "__main__":

    print(f"자동화 작업을 시작합니다: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        asyncio.run(run_total_automation("skdud1"))
    except Exception as e:
        print(f"에러 발생: {e}")
        exit(1) # 에러 발생 시 GitHub Actions에 실패를 알림

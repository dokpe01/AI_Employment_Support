import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__)) 
root_dir = os.path.dirname(current_dir) 

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from json_load import json_insert_to_enter 
from Data_collect.data_crawling import run_parallel_scraping
from Data_collect.duplicate import process_deduplication
from Data_collect.data_ocr import run_detail_process  
import Data_collect.LLM as LLM 


from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")

engine = create_async_engine(db_url)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_user_keywords(user_id):
    """DB에서 특정 사용자의 희망 직종을 가져옴"""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                text('SELECT job FROM "User" WHERE id = :id'),
                {"id": user_id}
            )
            row = result.fetchone()
            if row and row[0]:
                return [k.strip() for k in row[0].split(',')]
        except Exception as e:
            print(f" DB 키워드 조회 중 에러: {e}")
        return None
    
async def run_total_automation(job):
    start_total = time.time()
    # 추후 사용자가 선택한 직무가 들어가도록 수정 예정
    keywords = await get_user_keywords(job)
    if not keywords:
        print(f"사용자(ID: {id})의 희망직종이 설정되지 않았습니다.")
        return 

    #각 사이트에서 링크 크롤링 
    raw_list = run_parallel_scraping(keywords, max_items_per_site=20)

    #DB에 있는 기존 데이터들은 제거 
    async with AsyncSessionLocal() as session:
        # DB의 모든 URL을 가져옴 (또는 최근 2주치만 가져와도 충분)
        result = await session.execute(text('SELECT url FROM "Enter"'))
        existing_urls = {row[0] for row in result.fetchall()}
    
    # DB에 없는 새로운 공고만 남김
    new_raw_list = [job for job in raw_list if job.get('url') not in existing_urls]
    
    if not new_raw_list:
        print("새로운 공고가 없습니다. 작업을 종료합니다.")
        return
    
    data_dir = os.path.join(current_dir, "AI_Employment_Support", "data")
    os.makedirs(data_dir, exist_ok=True)

    raw_path = os.path.join(data_dir, "total_site_link_final.json")
    refined_path = os.path.join(data_dir, "refined_data.json")
    ocr_output_path = os.path.join(data_dir, "ocr_data.json")

    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(new_raw_list, f, ensure_ascii=False, indent=4)

    # 중복 공고 제거
    process_deduplication(raw_path, refined_path)

    #OCR
    run_detail_process(refined_path, ocr_output_path, workers=3)
    
    #LLM 가공 (비동기)
    await LLM.main()

    #DB저장
    json_insert_to_enter()

    end_total = time.time()
    print(f"\n 모든 자동화 공정 완료! (총 소요 시간: {round(end_total - start_total, 2)}초)")

if __name__ == "__main__":

    print(f"자동화 작업을 시작합니다: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        asyncio.run(run_total_automation("skdud1"))
    except Exception as e:
        print(f"에러 발생: {e}")
        exit(1) # 에러 발생 시 GitHub Actions에 실패를 알림



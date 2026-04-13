import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
import crud

from analysis.company_service import (
    get_company_news_data,
    generate_company_analysis
)


async def run_batch():
    db = SessionLocal()

    jobs = crud.get_enter_jobs_for_analysis(db, limit=5)

    prepared_jobs = []

    for job in jobs:
        company_name = job.name
        job_description = job.content or "공고 없음"

        print(f"[뉴스 수집] {company_name}")
        news = get_company_news_data(company_name)

        prepared_jobs.append({
            "enter_id": job.id,
            "company_name": company_name,
            "job_description": job_description,
            "news": news
        })

    tasks = [
        generate_company_analysis(
            item["company_name"],
            item["job_description"],
            item["news"]
        )
        for item in prepared_jobs
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for item, result in zip(prepared_jobs, results):
        if isinstance(result, Exception):
            print(f"[분석 실패] {item['company_name']}: {result}")
            report = "분석 실패"
        else:
            report = result

        crud.save_company_analysis(
            db,
            item["enter_id"],
            item["company_name"],
            item["job_description"],
            item["news"],
            report
        )

        print(f"[저장 완료] {item['company_name']}")

    db.close()


if __name__ == "__main__":
    asyncio.run(run_batch())
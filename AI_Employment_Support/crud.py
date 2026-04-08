from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
import models

from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy import func
import models

def get_recent_enters(db: Session, page: int = 1, size: int = 8, source: str = "전체"):
    query = db.query(models.Enter)

    if source and source != "전체":
        query = query.filter(models.Enter.source.ilike(f"%{source}%"))

    all_jobs = query.all()
    
    today = datetime.now().date()
    processed_jobs = []

    for job in all_jobs:
        try:
            if job.period and "~" in job.period:
                end_date_str = job.period.split('~')[-1].strip()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                job.remain_days = (end_date - today).days
                
                if job.remain_days < 0:
                    job.d_day = "마감"
                    job.sort_priority = 999
                elif job.remain_days == 0:
                    job.d_day = "D-Day"
                    job.sort_priority = 0
                else:
                    job.d_day = f"D-{job.remain_days}"
                    job.sort_priority = job.remain_days
            else:
                job.d_day = "상시"
                job.sort_priority = 500
        except:
            job.d_day = "상시"
            job.sort_priority = 500
        
        processed_jobs.append(job)

    processed_jobs.sort(key=lambda x: x.sort_priority)

    total_count = len(processed_jobs)
    skip = (page - 1) * size
    paged_jobs = processed_jobs[skip : skip + size]

    return paged_jobs, total_count

def get_ai_recommended_jobs(db: Session, user_id: str, limit: int = 4):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.skill:
        return []

    user_skills = [s.strip().lower() for s in user.skill.split(',')]
    all_jobs = db.query(models.Enter).all()
    scored_jobs = []

    for job in all_jobs:
        score = 0
        content = f"{job.job} {job.work or ''} {job.qual or ''} {job.prefer or ''}".lower()

        if user.job.lower() in job.job.lower(): score += 40
        for skill in user_skills:
            if skill in content: score += 15

        if score > 0:
            job.match_rate = min(score, 99) 
            job.status = "분석완료"
            scored_jobs.append(job)

    scored_jobs.sort(key=lambda x: x.match_rate, reverse=True)
    return scored_jobs[:limit]
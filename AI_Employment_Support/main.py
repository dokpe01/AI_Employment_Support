from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI()

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 테스트용 데이터에 'role' 키 추가
fake_job_db = [
    {
        "id": 1, 
        "company": "기아(KIA)", 
        "role": "Backend Engineer", # 직무 추가
        "title": "2026 상반기 신입 채용 (차세대 시스템 개발)", 
        "status": "분석완료"
    },
    {
        "id": 2, 
        "company": "현대자동차", 
        "role": "AI/ML Scientist", # 직무 추가
        "title": "전동화 제어 로직 최적화 및 AI 모델링", 
        "status": "대기중"
    },
]

@app.get("/", response_class=HTMLResponse)
async def read_list(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"jobs": fake_job_db}
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
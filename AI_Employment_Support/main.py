from fastapi import FastAPI, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
from dotenv import load_dotenv
from typing import List

load_dotenv()
KIT_ID = os.getenv("FA_KIT_ID")

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

fake_job_db = [
    {
        "id": 1, 
        "company": "기아(KIA)", 
        "role": "Backend Engineer",
        "title": "2026 상반기 신입 채용 (차세대 시스템 개발)", 
        "status": "분석완료"
    },
    {
        "id": 2, 
        "company": "현대자동차", 
        "role": "AI/ML Scientist",
        "title": "전동화 제어 로직 최적화 및 AI 모델링", 
        "status": "대기중"
    },
]

@app.get("/", response_class=HTMLResponse)
async def read_list(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"jobs": fake_job_db,
                 "kit_id" : KIT_ID}
    )

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="login.html", 
        context={"kit_id" : KIT_ID}
    )

@app.post("/login")
async def login_action(username: str = Form(...), password: str = Form(...)):
    if username == "admin" and password == "1234":
        return RedirectResponse(url="/", status_code=303)
    return RedirectResponse(url="/login?error=true", status_code=303)

@app.get("/check-id")
async def check_id(username: str):
    is_available = username not in ["admin", "testuser"] # 임시 로직
    return {"available": is_available}

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="signup.html",
        context={"kit_id": KIT_ID}
    )

@app.post("/signup")
async def signup_action(
    full_name: str = Form(...),
    email: str = Form(...),
    username: str = Form(...), 
    password: str = Form(...),
    confirm_password: str = Form(...),
    phone: str = Form(...),
    location: str = Form(...),
    desired_role: List[str] = Form(...),
    skills: str = Form(None),
    portfolio_urls: List[str] = Form(None)
):
    print(f"선택된 직무: {desired_role}")
    # 빈 문자열 제거 (사용자가 추가만 하고 입력 안 했을 경우 대비)
    valid_portfolios = [url for url in portfolio_urls if url.strip()] if portfolio_urls else []
    
    print(f"가입 시도 포트폴리오 리스트: {valid_portfolios}")

    if password != confirm_password:
        return RedirectResponse(url="/signup?error=password", status_code=303)
    
    user_data = {
        "name": full_name,
        "id": username,
        "email": email,
        "role": desired_role,
        "location": location,
        "skills": skills,
        "phone" : phone,
        "portfolio": portfolio_urls
    }
    print(f"가입 데이터: {user_data}")
    
    return RedirectResponse(url="/login", status_code=303)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
from fastapi import FastAPI, Request, Form, Depends, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
from dotenv import load_dotenv
from typing import List
import models, schemas, auth
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import crud
import math

try:
    from database import engine, SessionLocal
except ImportError:
    from .database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

load_dotenv(encoding="utf-8")
KIT_ID = os.getenv("FA_KIT_ID")

app = FastAPI()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def read_list(
    request: Request, 
    db: Session = Depends(get_db), 
    page: int = 1, 
    source: str = "전체"
):
    token = request.cookies.get("access_token")
    user = None
    user_id = None
    recommended_jobs = []

    if token:
        try:
            token_value = token.split(" ")[1]
            payload = jwt.decode(token_value, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
            user_id = payload.get("sub") 
            user = {"name": payload.get("user_name")}
            
            if user_id:
                all_recommended = crud.get_ai_recommended_jobs(db, user_id=user_id)
                
                recommended_jobs = [job for job in all_recommended if job.match_rate >= 60]
        except (JWTError, IndexError, AttributeError):
            user = None

    source_map = {"잡코리아": "JOBKOREA", "사람인": "SARAMIN", "잡플래닛": "JOBPLANET", "원티드": "WANTED"}
    db_source = source_map.get(source) if source != "전체" else "전체"

    size = 8
    recent_jobs, total_count = crud.get_recent_enters(db, page=page, size=size, source=db_source)
    total_pages = math.ceil(total_count / size)

    return templates.TemplateResponse(
        request=request, 
        name="index.html",
        context={
            "recommended_jobs": recommended_jobs,
            "recent_jobs": recent_jobs,
            "current_page": page,
            "total_pages": total_pages,
            "current_source": source,
            "kit_id": KIT_ID,
            "user": user
        }
    )

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="login.html", 
        context={"kit_id" : KIT_ID}
    )

@app.post("/login")
async def login_action(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == username).first()
    
    if not user:
        print(f"실패: DB에 '{username}'라는 아이디가 없습니다.")
        return RedirectResponse(url="/login?error=invalid", status_code=303)

    print(f"유저 확인: {user.name} (DB상의 ID: {user.id})")

    if not auth.verify_password(password, user.pw):
        print(f"실패: 비밀번호가 일치하지 않습니다.")
        return RedirectResponse(url="/login?error=invalid", status_code=303)

    access_token = auth.create_access_token(
        data={"sub": str(user.id), "user_name": user.name}
    )

    redirect_res = RedirectResponse(url="/", status_code=303)
    redirect_res.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token}", 
        httponly=True,  # 자바스크립트 탈취 방지
        max_age=60 * 60 * 24 # 1일 유지
    )
    
    print(f"로그인 성공! 메인 페이지로 이동합니다.")
    return redirect_res

@app.get("/check-id")
async def check_id(username: str):
    is_available = username not in ["admin", "testuser"] # 임시 로직
    return {"available": is_available}

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response

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
    portfolio_urls: List[str] = Form(None),
    db: Session = Depends(get_db)
):
    if password != confirm_password:
        return RedirectResponse(url="/signup?error=password", status_code=303)

    existing_user = db.query(models.User).filter(
        (models.User.email == email) | (models.User.id == username)
    ).first()
    
    if existing_user:
        return RedirectResponse(url="/signup?error=exists", status_code=303)

    role_str = ", ".join(desired_role) if desired_role else ""
    valid_portfolios = ", ".join([url for url in portfolio_urls if url.strip()]) if portfolio_urls else ""
    
    pw_bytes = password.encode("utf-8")
    truncated_pw = bcrypt.gensalt()
    hashed_password_bytes = bcrypt.hashpw(pw_bytes, truncated_pw)
    hashed_password = hashed_password_bytes.decode("utf-8")

    new_user = models.User(
        id=username,
        pw=hashed_password,
        job=role_str,
        location=location,
        url=valid_portfolios,
        skill=skills,
        email=email,
        phone=phone,
        name=full_name
    )

    try:
        db.add(new_user)
        db.commit()
        print(f"DB 가입 성공: {full_name}")
        return RedirectResponse(url="/login", status_code=303)
    except Exception as e:
        db.rollback()
        print(f"DB 저장 에러: {e}")
        return RedirectResponse(url="/signup?error=db", status_code=303)
    
@app.get("/profile", response_class=HTMLResponse)
async def get_profile(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=303)

    try:
        token_value = token.split(" ")[1]
        payload = jwt.decode(token_value, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        user_id = payload.get("sub")
    except (JWTError, IndexError):
        return RedirectResponse(url="/login", status_code=303)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "user":user,
            "kit_id":KIT_ID
        }
    )

@app.get("/profile/edit", response_class=HTMLResponse)
async def edit_profile_page(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token: return RedirectResponse(url="/login", status_code=303)

    try:
        token_value = token.split(" ")[1]
        payload = jwt.decode(token_value, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        user_id = payload.get("sub")
    except: return RedirectResponse(url="/login", status_code=303)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    return templates.TemplateResponse(
        request=request,
        name="profile_edit.html",
        context={"user": user, "kit_id": KIT_ID}
    )

@app.post("/profile/update")
async def update_profile(
    request: Request,
    name: str = Form(...),
    job: str = Form(None),
    skill: str = Form(None),
    phone: str = Form(None),
    location: str = Form(None),
    url: str = Form(None),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    token_value = token.split(" ")[1]
    payload = jwt.decode(token_value, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    user_id = payload.get("sub")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.name = name
        user.job = job
        user.skill = skill
        user.phone = phone
        user.location = location
        user.url = url
        db.commit()

    return RedirectResponse(url="/profile", status_code=303)

@app.get("/interview", response_class=HTMLResponse)
async def interview_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)

    try:
        token_value = str(token).replace("Bearer ", "").strip()
        
        payload = jwt.get_unverified_claims(token_value)
        u_name = str(payload.get("user_name", "사용자"))

        template = templates.get_template("interview.html")
        
        content = template.render({
            "request": request,
            "itv_user_name": u_name,
            "kit_id": KIT_ID
        })
        
        return HTMLResponse(content=content)

    except Exception as e:
        print(f"DEBUG: FATAL_ERROR_LOG -> {type(e).__name__}: {str(e)}")
        return RedirectResponse(url="/login", status_code=302)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
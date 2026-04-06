import json
import time
import requests
import cv2
import numpy as np
import pytesseract
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


# 1. OCR 설정
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def perform_ocr(image_url):
    """이미지 URL에서 실시간으로 텍스트 추출"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(image_url, headers=headers, timeout=5)
        img = Image.open(BytesIO(res.content))
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
        cv_img = cv2.threshold(cv_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        return pytesseract.image_to_string(cv_img, lang='kor+eng', config='--psm 3').strip()
    except:
        return ""


def get_fast_driver():
    """배포용 최적화 드라이버 설정 (Headless & No-Image)"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
   
    # 알림/위치 권한 차단
    prefs = {"profile.default_content_setting_values.notifications": 2, "profile.default_content_setting_values.geolocation": 2}
    options.add_experimental_option("prefs", prefs)
   
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def process_single_job(job):
    """개별 공고를 처리하는 핵심 함수 (각 스레드에서 실행)"""
    driver = get_fast_driver()
    try:
        driver.get(job['url'])
        time.sleep(2) # 로딩 대기


        content = ""
        # --- 사이트별 추출 로직 ---
        if job['source'] == 'wanted':
            try:
                driver.execute_script("document.querySelector('button[class*=\"more_button\"]').click();")
                time.sleep(0.5)
            except: pass
            content = driver.find_element(By.CSS_SELECTOR, "article[class*='JobDescription']").text.strip()


        elif job['source'] == 'jobplanet':
            content = "\n".join([s.text for s in driver.find_elements(By.CSS_SELECTOR, "section[class*='detail']")]).strip()


        elif job['source'] in ['saramin', 'jobkorea']:
            try:
                iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[id*='iframe'], #gib_frame")
                if iframes:
                    driver.switch_to.frame(iframes[0])
                    content = driver.find_element(By.TAG_NAME, "body").text.strip()
                else:
                    content = driver.find_element(By.CSS_SELECTOR, ".user_content, .job_detail").text.strip()
            except: content = ""


        # --- 실시간 조건부 OCR ---
        if len(content) < 200:
            collected_imgs = set()
            imgs = driver.find_elements(By.TAG_NAME, "img")
            ocr_texts = []
            for img in imgs:
                src = img.get_attribute('src')
                if src and 'logo' not in src.lower() and 'http' in src:
                    collected_imgs.add(src)
                    res = perform_ocr(src)
                    if len(res) > 30: ocr_texts.append(res)
            job["image_urls"] = list(collected_imgs)
           
            if ocr_texts:
                content += "\n\n[이미지 추출 내용]\n" + "\n".join(ocr_texts)


        job['content'] = content
        return job


    except Exception as e:
        print(f"❌ [에러] {job['source']}: {e}")
        job['content'] = "수집 실패"
        return job
    finally:
        driver.quit()


# --- 메인 통합 실행부 ---
if __name__ == "__main__":
    # 1. 1단계 결과 파일 로드
    with open("total_site_link.json", "r", encoding="utf-8") as f:
        job_list = json.load(f)


    print(f"🚀 병렬 수집 엔진 가동 (대상: {len(job_list)}건)")
   
    start_time = time.time()


    # 2. 멀티스레딩 실행 (max_workers=4는 브라우저 4개를 동시에 띄운다는 뜻)
    # CPU/메모리 사양에 따라 2~8 사이로 조절하세요.
    with ThreadPoolExecutor(max_workers=2) as executor:
        final_results = list(executor.map(process_single_job, job_list))


    end_time = time.time()


    # 3. 결과 저장
    with open("ocr_data.json", "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=4)


    print(f"\n 전 과정 완료!")
    print(f" 총 소요 시간: {round(end_time - start_time, 2)}초 (평균 {round((end_time - start_time)/len(job_list), 2)}초/건)")



import pytesseract
import fitz  
from PIL import Image
import os

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text_pdf(pdf_path):
    with fitz.open(pdf_path) as doc:
        full_content = ""

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            text = page.get_text()

            if text.strip():
                full_content += text + "\n"

            else:
                pix = page.get_pixmap(matrix=fitz.Matrix(4, 4))  # 4배 확대
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_string(img, lang='kor+eng')
                full_content += text + "\n"
    return full_content

def save_to_txt(content, output_path):
    """추출된 텍스트를 txt 파일로 저장"""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

    except Exception as e:
        print(f"❌ 저장 실패: {e}")


if __name__ == "__main__":
    pdf_path = "./data/resume.pdf"
    txt_output_path = pdf_path.replace(".pdf", ".txt")

    result = extract_text_pdf(pdf_path)
        
    if result.strip():
        save_to_txt(result, txt_output_path)
    else:
        print("추출된 텍스트가 없습니다. PDF 내용을 확인해주세요.")

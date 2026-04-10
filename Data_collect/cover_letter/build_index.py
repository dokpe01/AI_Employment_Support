import os
import json
import faiss
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

MODEL_NAME = "intfloat/multilingual-e5-base"


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        value = value.strip()
        if not value or value == "미기재":
            return []
        return [value]
    return [str(value).strip()]


def ensure_text(value, default="미기재"):
    if value is None:
        return default
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
        return ", ".join(items) if items else default
    value = str(value).strip()
    return value if value else default


def make_document_text(item):
    name = ensure_text(item.get("name"))
    period = ensure_text(item.get("period"))
    job = ensure_text(item.get("job"))
    location = ensure_text(item.get("location"))
    work = ensure_text(item.get("work"))
    qual = ensure_text(item.get("qual"))
    prefer = ensure_text(item.get("prefer"))
    procedure = ensure_text(item.get("procedure"))
    docs = ensure_text(item.get("docs"))
    apply = ensure_text(item.get("apply"))
    career = ensure_text(item.get("career"))
    source = ensure_text(item.get("source"))
    collected_at = ensure_text(item.get("collected_at"))
    url = ensure_text(item.get("url"))

    return "\n".join([
        f"기업명: {name}",
        f"모집기간: {period}",
        f"직무: {job}",
        f"근무지: {location}",
        f"주요업무: {work}",
        f"자격요건: {qual}",
        f"우대사항: {prefer}",
        f"채용절차: {procedure}",
        f"제출서류: {docs}",
        f"지원방법: {apply}",
        f"경력: {career}",
        f"출처: {source}",
        f"수집일시: {collected_at}",
        f"URL: {url}",
    ])


def make_summary_text(item):
    name = ensure_text(item.get("name"))
    job = ensure_text(item.get("job"))
    location = ensure_text(item.get("location"))
    career = ensure_text(item.get("career"))

    qual_list = ensure_list(item.get("qual"))[:3]
    prefer_list = ensure_list(item.get("prefer"))[:2]

    qual_part = ", ".join(qual_list) if qual_list else "자격요건 미기재"
    prefer_part = ", ".join(prefer_list) if prefer_list else "우대사항 미기재"

    return (
        f"{name}의 {job} 채용 공고. "
        f"근무지는 {location}, 경력 조건은 {career}. "
        f"주요 자격요건은 {qual_part}이며, 우대사항은 {prefer_part}."
    )


def build_index():
    input_path = os.path.join(DATA_DIR, "LLM_data.json")
    index_path = os.path.join(DATA_DIR, "jobs_faiss.index")
    meta_path = os.path.join(DATA_DIR, "jobs_metadata.json")

    with open(input_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    docs = []
    for idx, item in enumerate(raw_data):
        document_text = make_document_text(item)
        summary_text = make_summary_text(item)

        docs.append({
            "faiss_id": idx,
            "name": ensure_text(item.get("name")),
            "job": ensure_text(item.get("job")),
            "location": ensure_text(item.get("location")),
            "career": ensure_text(item.get("career")),
            "source": ensure_text(item.get("source")),
            "url": ensure_text(item.get("url")),
            "document_text": document_text,
            "summary_text": summary_text,
            "metadata": item
        })

    model = SentenceTransformer(MODEL_NAME)
    embedding_texts = [f"passage: {doc['document_text']}" for doc in docs]

    embeddings = model.encode(
        embedding_texts,
        normalize_embeddings=True,
        convert_to_numpy=True
    ).astype("float32")

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    faiss.write_index(index, index_path)

    metadata_map = {
        str(doc["faiss_id"]): {
            "company_name": doc["name"],
            "job": doc["job"],
            "location": doc["location"],
            "career": doc["career"],
            "source": doc["source"],
            "url": doc["url"],
            "summary_text": doc["summary_text"],
            "document_text": doc["document_text"],
            "job_posting": doc["metadata"]
        }
        for doc in docs
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata_map, f, ensure_ascii=False, indent=2)

    print(f"총 {len(docs)}개 문서를 FAISS에 저장했습니다.")


if __name__ == "__main__":
    build_index()
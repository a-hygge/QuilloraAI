# LibMate AI — Web Demo

> Người bạn đọc sách thông minh cho Thư viện PTIT.
> Bản web demo (FastAPI + HTML một trang) — phục vụ vòng sơ khảo.

## Tính năng demo

1. **Khám phá thư viện** — duyệt 3 cuốn sách mẫu đã được ingest.
2. **Chat với sách (B1)** — hỏi tự nhiên, trả lời có trích dẫn chương/đoạn nguồn.
3. **Tóm tắt / Quiz / Flashcard** — sinh tài liệu ôn tập từ 1 cú click.
4. **Hình hoá đoạn văn (D1)** — nhập excerpt → sinh ảnh minh hoạ (fal.ai LCM).
5. **Voice chat (C1)** — endpoint WebSocket `/ws/voice` đã có sẵn, dùng Gemini Live.

## Kiến trúc gọn nhẹ

```
LibMateAI/
├── app/
│   ├── main.py           # FastAPI entry + mount static
│   ├── config.py         # Env settings
│   ├── storage.py        # JSON-file store (books, chunks)
│   ├── rag.py            # Ingest + retrieve (sentence-transformers + cosine)
│   ├── llm.py            # Gemini wrapper
│   └── routers/
│       ├── library.py    # GET /api/library/books
│       ├── reader.py     # POST /api/reader/{book_id}/ask|quiz|summary|flashcards
│       ├── visualize.py  # POST /api/visualize
│       └── voice.py      # WS  /ws/voice (Gemini Live stub)
├── web/
│   ├── index.html        # Single-page UI
│   └── static/
│       ├── style.css     # LibMate theme: ivory + terracotta + deep blue
│       └── app.js
├── data/
│   ├── books.json        # Metadata (tạo bởi scripts/ingest.py)
│   ├── chunks.json       # Chunks + embeddings
│   └── sample_books/     # Nguồn text mẫu
├── scripts/
│   └── ingest.py         # Seed 3 sách mẫu và build vector index
├── requirements.txt
├── .env.example
└── README.md
```

## Chạy local (không Docker)

```bash
cd LibMateAI
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

cp .env.example .env           # rồi mở file .env và điền GEMINI_API_KEY + FAL_API_KEY

python -m scripts.ingest       # Ingest 3 sách mẫu vào data/
uvicorn app.main:app --reload  # http://localhost:8000
```

Mở trình duyệt: <http://localhost:8000>

## Chạy bằng Docker

```bash
cd LibMateAI
cp .env.example .env           # điền GEMINI_API_KEY (và FAL_API_KEY nếu có)

docker compose build
docker compose run --rm libmate python -m scripts.ingest   # seed lần đầu
docker compose up -d
# http://localhost:8000
```

- Thư mục `./data` được mount vào container nên `books.json` và `chunks.json`
  vẫn tồn tại sau khi rebuild/restart.
- Xem log: `docker compose logs -f libmate`
- Dừng: `docker compose down`

## Biến môi trường tối thiểu

| Biến             | Bắt buộc | Ghi chú                                 |
|------------------|----------|-----------------------------------------|
| `GEMINI_API_KEY` | ✅       | Dùng cho chat/quiz/summary/voice        |
| `FAL_API_KEY`    | Khuyên   | Visualize; nếu không có sẽ dùng ảnh stub |

## Demo flow 5 phút (gợi ý)

1. Mở Thư viện → chọn "Mạng máy tính cơ bản".
2. Bấm **Chat** → hỏi *"Giải thích TCP bắt tay ba bước"* → xem trích dẫn.
3. Bấm **Tóm tắt** → nhận summary 200 từ.
4. Bấm **Quiz** → 5 MCQ độ khó Medium.
5. Mở "Số đỏ" → paste 1 đoạn → **Visualize** → ảnh minh hoạ.
6. (Optional) Mic → Voice chat với "linh hồn cuốn sách".

## Tái sử dụng từ 2 codebase

| Module                | Nguồn               | Trạng thái |
|-----------------------|---------------------|------------|
| RAG chunking + retrieve | `EduMentorAI/indexing`, `EduMentorAI/retrievers` | Rút gọn sang `app/rag.py` |
| Gemini Live WebSocket   | `p-inno-drawing/routers/voice_chat.py`           | `app/routers/voice.py` (giữ giao thức) |
| fal.ai LCM image gen    | `p-inno-drawing/services/fal.py`                  | `app/services/visualize` (stub-able) |
| FastAPI boilerplate     | `p-inno-drawing/main.py`, `core/config.py`        | `app/main.py`, `app/config.py` |

## Ghi chú

- Bản demo không cần PostgreSQL/Milvus — dữ liệu và vector lưu ở `data/*.json` để chạy ngay trong 1 phút.
- Khi đóng gói chung khảo sẽ chuyển sang Milvus + Postgres theo schema ở `LibMateAI_Proposal.md §5`.

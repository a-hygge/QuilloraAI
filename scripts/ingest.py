"""Seed 3 sample books and build the vector index.

Run: python -m scripts.ingest
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running as `python -m scripts.ingest` from project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import rag, storage  # noqa: E402


SAMPLE_BOOKS: list[dict] = [
    {
        "id": 1,
        "title": "Mạng máy tính cơ bản",
        "authors": ["PTIT Press"],
        "language": "vi",
        "category": "Giáo trình",
        "difficulty": 3,
        "cover_emoji": "🌐",
        "ai_summary": (
            "Giáo trình nhập môn về mạng máy tính: mô hình OSI, TCP/IP, bắt tay ba "
            "bước, định tuyến, và bảo mật cơ bản."
        ),
        "keywords": ["TCP/IP", "OSI", "định tuyến", "bảo mật"],
        "chapters": [
            {
                "chapter": "Chương 1 — Mô hình OSI",
                "page": 12,
                "text": (
                    "Mô hình OSI (Open Systems Interconnection) chia chức năng mạng thành 7 tầng: "
                    "Physical, Data Link, Network, Transport, Session, Presentation, Application. "
                    "Mỗi tầng đóng gói dữ liệu từ tầng trên và bổ sung header riêng, tạo nên quá trình "
                    "encapsulation. Ở phía nhận, các tầng thực hiện de-encapsulation ngược lại. "
                    "Việc chia tầng giúp các nhà phát triển thiết kế giao thức độc lập, dễ thay thế "
                    "và mở rộng mà không ảnh hưởng các tầng khác."
                ),
            },
            {
                "chapter": "Chương 2 — TCP và bắt tay ba bước",
                "page": 34,
                "text": (
                    "TCP là giao thức hướng kết nối tại tầng Transport, đảm bảo truyền dữ liệu tin cậy, "
                    "có thứ tự và kiểm soát tắc nghẽn. Trước khi trao đổi dữ liệu, TCP thiết lập kết nối "
                    "bằng bắt tay ba bước (three-way handshake): (1) Client gửi gói SYN với số sequence "
                    "khởi tạo; (2) Server trả lời SYN-ACK xác nhận và đính kèm sequence của mình; "
                    "(3) Client gửi ACK để hoàn tất. Sau ba bước này, cả hai phía đều xác nhận khả năng "
                    "gửi và nhận dữ liệu, kết nối chính thức mở. Đóng kết nối sử dụng FIN/ACK bốn bước."
                ),
            },
            {
                "chapter": "Chương 3 — Định tuyến IP",
                "page": 58,
                "text": (
                    "Định tuyến IP là quá trình chọn đường đi cho gói tin giữa các mạng. Các giao thức "
                    "phổ biến gồm RIP (dựa trên vector khoảng cách), OSPF (trạng thái liên kết, dùng "
                    "thuật toán Dijkstra), và BGP (giữa các hệ tự trị). Bảng định tuyến trên router "
                    "chứa các entry (prefix, next-hop, metric). Khi nhận một gói, router so khớp prefix "
                    "dài nhất (longest prefix match) để chọn đường đi phù hợp nhất."
                ),
            },
            {
                "chapter": "Chương 4 — An toàn mạng căn bản",
                "page": 92,
                "text": (
                    "An toàn mạng bao gồm ba trụ cột: Confidentiality, Integrity, Availability (CIA). "
                    "Các cơ chế thường dùng là mã hoá đối xứng (AES), bất đối xứng (RSA, ECC), hàm băm "
                    "(SHA-256), và chứng chỉ số X.509. TLS kết hợp các thành phần này để bảo vệ kênh "
                    "truyền HTTPS. Bên cạnh đó, tường lửa và hệ thống phát hiện xâm nhập (IDS) giúp "
                    "kiểm soát luồng và cảnh báo sự cố."
                ),
            },
        ],
    },
    {
        "id": 2,
        "title": "Số đỏ",
        "authors": ["Vũ Trọng Phụng"],
        "language": "vi",
        "category": "Văn học",
        "difficulty": 2,
        "cover_emoji": "📗",
        "ai_summary": (
            "Tiểu thuyết trào phúng kinh điển xoay quanh Xuân Tóc Đỏ, một kẻ vô học nhờ thời cuộc "
            "bỗng trở thành 'danh nhân' trong xã hội thành thị nửa Tây nửa ta đầu thế kỷ 20."
        ),
        "keywords": ["trào phúng", "thành thị", "phong hoá"],
        "chapters": [
            {
                "chapter": "Chương 1 — Phố phường",
                "page": 1,
                "text": (
                    "Hà Nội những năm 1930 ồn ào dưới bầu trời xám. Các tiệm may Âu phục mọc lên san "
                    "sát, tiếng rao hàng hoà lẫn tiếng còi tàu điện. Trên hè phố, những quý bà diện áo "
                    "dài tân thời sánh bước cùng các ông tham tóc chải dầu bóng lộn. Ở một góc công "
                    "viên, Xuân Tóc Đỏ — một tay nhặt banh quần vợt — đứng ngáp dài, mơ hồ nghĩ về "
                    "vận may lớn mà hắn đoan chắc một ngày sẽ gõ cửa."
                ),
            },
            {
                "chapter": "Chương 5 — Cuộc đổi đời",
                "page": 74,
                "text": (
                    "Chỉ sau vài lời nói trúng ý bà Phó Đoan, Xuân bỗng được coi như một nhà cải cách "
                    "xã hội. Hắn được mời tới các salon sang trọng, được giới thiệu là 'chuyên gia Âu "
                    "hoá', dù hắn chưa từng đặt chân ra khỏi Hà Nội. Vũ Trọng Phụng đặc tả cảnh đổi đời "
                    "chóng mặt ấy bằng giọng văn trào phúng chua chát: những lời tán tụng rỗng tuếch, "
                    "những cái bắt tay đầy toan tính, và phía sau là sự mục ruỗng đạo đức của một xã hội "
                    "đang chạy theo cái mới nửa vời."
                ),
            },
            {
                "chapter": "Chương 12 — Đám tang gương mẫu",
                "page": 188,
                "text": (
                    "Cụ cố Hồng qua đời. Cả đại gia đình hân hoan chuẩn bị một đám tang 'to nhất kinh "
                    "thành'. Người ta khoe khăn trắng mới may, khoe bộ com-lê đen mượn của hiệu Tây, "
                    "bàn tán về ảnh chụp đăng báo. Xuân Tóc Đỏ, nay đã là 'đốc tờ', xuất hiện với tư "
                    "cách danh dự. Không ai thực sự khóc; tất cả là sân khấu. Qua ngòi bút sắc bén của "
                    "tác giả, đám tang trở thành bức biếm hoạ về cái gọi là 'văn minh'."
                ),
            },
        ],
    },
    {
        "id": 3,
        "title": "Nhập môn Trí tuệ Nhân tạo",
        "authors": ["PTIT Press"],
        "language": "vi",
        "category": "Giáo trình",
        "difficulty": 4,
        "cover_emoji": "🤖",
        "ai_summary": (
            "Giáo trình nhập môn AI: tìm kiếm, học máy có giám sát, mạng nơ-ron sâu, và các ứng dụng "
            "thực tế như xử lý ngôn ngữ tự nhiên và thị giác máy tính."
        ),
        "keywords": ["AI", "machine learning", "deep learning", "NLP"],
        "chapters": [
            {
                "chapter": "Chương 1 — Tác tử và tìm kiếm",
                "page": 10,
                "text": (
                    "Một tác tử (agent) là thực thể quan sát môi trường qua cảm biến và tác động trở lại "
                    "qua bộ chấp hành. Các thuật toán tìm kiếm cơ bản gồm BFS (duyệt theo chiều rộng, "
                    "đảm bảo đường đi ngắn nhất theo số bước), DFS (theo chiều sâu, tiết kiệm bộ nhớ "
                    "nhưng có thể đi vào nhánh cụt), và A* (tìm kiếm có thông tin, dùng hàm heuristic "
                    "đảm bảo tối ưu nếu heuristic chấp nhận được)."
                ),
            },
            {
                "chapter": "Chương 3 — Học có giám sát",
                "page": 48,
                "text": (
                    "Học có giám sát huấn luyện mô hình trên cặp dữ liệu (x, y) để học hàm ánh xạ. "
                    "Các thuật toán kinh điển bao gồm hồi quy tuyến tính, hồi quy logistic, cây quyết "
                    "định, SVM và k-NN. Quá trình huấn luyện tối thiểu hoá hàm mất mát; các kỹ thuật "
                    "regularization (L1, L2) giúp chống overfitting. Đánh giá mô hình dùng các metric "
                    "như accuracy, precision, recall, F1 và ROC-AUC."
                ),
            },
            {
                "chapter": "Chương 6 — Mạng nơ-ron sâu",
                "page": 112,
                "text": (
                    "Mạng nơ-ron sâu gồm nhiều tầng ẩn nối tiếp với hàm kích hoạt phi tuyến (ReLU, "
                    "GELU). Quá trình huấn luyện dựa trên lan truyền ngược (backpropagation) và "
                    "gradient descent (SGD, Adam). Các kiến trúc tiêu biểu: CNN cho ảnh, RNN/LSTM cho "
                    "chuỗi, và Transformer — hiện đang thống trị lĩnh vực xử lý ngôn ngữ tự nhiên "
                    "nhờ cơ chế self-attention cho phép học phụ thuộc dài."
                ),
            },
            {
                "chapter": "Chương 9 — RAG và ứng dụng",
                "page": 182,
                "text": (
                    "Retrieval-Augmented Generation (RAG) kết hợp một bộ tìm kiếm ngữ nghĩa với một "
                    "mô hình sinh ngôn ngữ lớn. Quy trình: tài liệu được chia đoạn, nhúng thành vector "
                    "và lưu vào vector database; khi có truy vấn, hệ thống lấy top-k đoạn phù hợp làm "
                    "ngữ cảnh cho LLM sinh câu trả lời có dẫn nguồn. RAG giảm ảo giác (hallucination) "
                    "và cho phép cập nhật tri thức mà không cần huấn luyện lại mô hình."
                ),
            },
        ],
    },
]


def main() -> None:
    books_out = []
    chunks_out: list[dict] = []
    chunk_id = 1

    all_texts: list[str] = []
    meta: list[tuple[int, str, int]] = []

    for b in SAMPLE_BOOKS:
        books_out.append(
            {
                "id": b["id"],
                "title": b["title"],
                "authors": b["authors"],
                "language": b["language"],
                "category": b["category"],
                "difficulty": b["difficulty"],
                "cover_emoji": b.get("cover_emoji", "📚"),
                "ai_summary": b["ai_summary"],
                "keywords": b["keywords"],
                "num_chapters": len(b["chapters"]),
            }
        )
        for ch in b["chapters"]:
            # Chapter text is already reasonably chunked; one chunk = one chapter.
            all_texts.append(ch["text"])
            meta.append((b["id"], ch["chapter"], ch["page"]))

    print(f"[ingest] Embedding {len(all_texts)} chunks with {len(books_out)} books...")
    vecs = rag.embed_texts(all_texts)

    for (book_id, chapter, page), text, vec in zip(meta, all_texts, vecs):
        chunks_out.append(
            {
                "id": chunk_id,
                "book_id": book_id,
                "chapter": chapter,
                "page": page,
                "text": text,
                "embedding": vec,
            }
        )
        chunk_id += 1

    storage.save_books(books_out)
    storage.save_chunks(chunks_out)
    rag.refresh_index()
    print(f"[ingest] Done. Saved {len(books_out)} books, {len(chunks_out)} chunks.")


if __name__ == "__main__":
    main()

# Kiểm tra bảo mật và dependency — 2026-10-04

## 1. Cache npm trong Git

Xác nhận 991 file `backend/.sites-runtime/` được theo dõi ở HEAD ban đầu.
Đã đổi ignore thành `.sites-runtime/` ở mọi cấp và bỏ các file này khỏi
index bằng `git rm --cached`; cache trên ổ đĩa được giữ lại.

Đã dùng git-filter-repo 2.47.0 trên bản sao độc lập, lọc
`--path-regex '(^|/)\.sites-runtime/' --invert-paths`.
Loại các ref nội bộ `refs/codex/` khỏi **bản sao** trước khi đóng gói.

- Git pack gốc: **192,65 MiB**; bản sạch: **1,88 MiB**.
- Đối chiếu mode, đường dẫn và blob ID của mọi file ngoài cache trong cả 7
  commit: không thay đổi. Không còn đường dẫn cache trong lịch sử bản sạch.
- `git fsck --full` và `git bundle verify` đạt.
- Bản sạch: `.sites-runtime/history-clean.git` và `.sites-runtime/history-clean.bundle`.
- Bằng chứng: `.sites-runtime/history-verification.json`; ánh xạ SHA:
  `.sites-runtime/history-clean.git/filter-repo/commit-map`.

Hai nhánh trong bundle:

| Nhánh | SHA cũ | SHA sạch |
| --- | --- | --- |
| `feat/initial-project` | `ae37ea9` | `2b6e0e3` |
| `main` | `f439a89` | `6ed5046` |

**Cập nhật 2026-10-08: lịch sử remote đã được ghi lại.** Lọc lại từ các ref
mới nhất, loại thêm `backend/.pytest-tmp-codex-baseline/` (thư mục tạm pytest bị
commit nhầm), đối chiếu cây file của cả 10 commit (khớp ngoài hai thư mục bị
loại), rồi cập nhật `main`, `feat/initial-project` và
`claude/youthful-meitner-0kodvk` bằng `--force-with-lease` với SHA remote đã
kiểm chứng. Pack: 192,37 MiB → 1,86 MiB.

| Nhánh | SHA cũ | SHA mới |
| --- | --- | --- |
| `main` | `f439a89` | `6ed5046` |
| `feat/initial-project` | `5d66c4c` | `904d343` |
| `claude/youthful-meitner-0kodvk` | `9566d9b` | `e08ccf2` |

Mọi bản clone cũ phải clone lại (hoặc `git fetch` rồi `git reset --hard
origin/<nhánh>` sau khi lưu thay đổi chưa commit) và không được merge lịch sử cũ
trở lại. GitHub có thể còn giữ object cũ trong cache hoặc qua ref khác cho tới
khi thu gom.

## 2. Header danh tính

[Tài liệu Sites](https://learn.chatgpt.com/docs/sites) quy định chuyển danh
tính qua `oai-authenticated-user-email` và header tên tùy chọn. Trang này
không nêu giao thức chữ ký/HMAC để ứng dụng tự xác minh. Vì vậy, không tự
đặt ra một giao thức chữ ký rồi coi đó là tương thích với Sites.

Trong repo hiện tại không có nơi gọi helper `getChatGPTUser` ngoài file khai
báo. Chưa có bằng chứng khai thác hay bằng chứng về chính sách strip header
của ingress đang triển khai.

Đã tách parser có kiểm thử và mặc định từ chối mọi header danh tính khi
`MEDDIES_AUTH_MODE` không phải `sites-proxy`. Header từ request không thể bật
chế độ này. Chỉ cấu hình biến môi trường phía server này khi đã xác nhận:

- Request chỉ có thể đi qua ingress Sites; không có đường truy cập origin trực tiếp.
- Ingress loại bỏ hoặc ghi đè header danh tính do client gửi.

Đây là cấu hình tin cậy proxy, **không phải xác thực chữ ký**. Nếu chưa chứng
minh được hai điều kiện trên, giữ `disabled` hoặc dùng cơ chế session/token
có xác minh tại server. Không dùng header này để cấp quyền ở backend FastAPI;
backend hiện vẫn là API không yêu cầu đăng nhập.

## 3. Giới hạn API

`/triage` chạy luật xác định, không gọi LLM. Trước đợt sửa, Pydantic đã giới
hạn trường và tổng độ dài hội thoại nhưng chưa chặn body HTTP lớn trước khi
parse JSON.

Middleware ASGI mới áp dụng cho POST trên cả ba endpoint, trước handler:

| Biến môi trường | Mặc định |
| --- | --- |
| `MEDDIES_MAX_REQUEST_BYTES` | 262144 byte |
| `MEDDIES_BODY_TIMEOUT_SECONDS` | 15 giây |
| `MEDDIES_RATE_WINDOW_SECONDS` | 60 giây |
| `MEDDIES_RATE_TRIAGE` | 120 request/IP/cửa sổ |
| `MEDDIES_RATE_CONSULTATION` | 20 request/IP/cửa sổ |
| `MEDDIES_RATE_RAG_SEARCH` | 60 request/IP/cửa sổ |
| `MEDDIES_RATE_GLOBAL` | 120 request/cửa sổ cho cả ba endpoint |
| `MEDDIES_RATE_MAX_CLIENTS` | 4096 cặp IP/endpoint |
| `MEDDIES_MAX_INFLIGHT_REQUESTS` | 8 request đang xử lý |

Đếm byte thực tế kể cả chunked/missing/khai sai Content-Length; body quá lớn
trả 413, vượt tốc độ trả 429 + Retry-After, quá tải đồng thời trả 503.
Từ chối body nén và Content-Length không hợp lệ. Các bucket hết hạn được
dọn, không đẩy bucket đang hoạt động ra để tạo lỗ hổng né hạn mức.

Hai script chạy local thêm `--no-proxy-headers`. Middleware dùng IP từ ASGI;
nếu triển khai qua proxy, chỉ cho Uvicorn tin đúng proxy đã được kiểm chứng,
không cấu hình tin mọi địa chỉ gửi X-Forwarded-For.

Quota này nằm trong RAM **mỗi process**, mất khi restart. Khi chạy nhiều
worker/replica hoặc cung cấp API công khai, cần quota dùng chung ở gateway
và giới hạn ngân sách nhà cung cấp. CORS không thay thế xác thực hay quota.
Endpoint health/ready và CORS preflight không tiêu hao quota này.

## 4. Prompt injection

Prompt grounded ban đầu đã có quy tắc bỏ qua chỉ dẫn độc hại. Điểm yếu rõ
hơn là dữ liệu RAG/trạng thái được đưa vào message `system`, còn nhánh hỏi
thêm và degraded chưa có cùng chính sách phân tách dữ liệu.

Cả ba nhánh sinh câu trả lời giờ chỉ có một message `system` chứa chỉ dẫn
tĩnh, và một message `user` chứa JSON của dữ liệu hội thoại/trạng thái/RAG.
Lịch sử vai trò assistant từ trình duyệt cũng chỉ là dữ liệu không đáng tin.
Escape `<`/`>` trong JSON để chuỗi như `<|im_start|>` không trở thành token
đổi vai trò của Qwen; vẫn bảo toàn giá trị văn bản khi giải mã JSON.

Giữ kiểm tra cấp cứu xác định trước LLM/RAG và giữ kiểm tra citation.
Không xóa tùy tiện nội dung triệu chứng bằng blacklist. Phân tách vai trò
và escape token giảm bề mặt tấn công, **không chứng minh chống mọi prompt
injection ngữ nghĩa**. Các test dùng spy/stub kiểm chứng cấu trúc và routing;
cần đánh giá đối kháng trên model/adapter thật trước khi dùng production.

## 5. Phiên bản và độ ổn định

| Thành phần | Kết quả đối chiếu |
| --- | --- |
| Next 16.2.6 | [Bản phát hành chính thức](https://github.com/vercel/next.js/releases/tag/v16.2.6), có sửa bảo mật; không phải phiên bản giả định. |
| React 19.2.6 | [Bản phát hành 2026-05-06](https://github.com/react/react/releases/tag/v19.2.6). |
| Node 22/24 | [Hai dòng LTS](https://nodejs.org/en/about/previous-releases) tại thời điểm kiểm tra; production nên dùng patch còn hỗ trợ trong dòng LTS. `>=22.13` chỉ là ngưỡng tương thích, không phải lock production. |
| Transformers 4.57.6 | [Có trên PyPI](https://pypi.org/project/transformers/4.57.6/); máy hiện tại cài đúng bản này. |
| PyTorch/CUDA | [PyTorch 2.5.1 có các build CUDA 11.8/12.1/12.4 và CPU](https://pytorch.org/get-started/previous-versions/). CUDA 12.4 là lựa chọn trong Conda, không phải yêu cầu chung của mọi torch/transformers. |

Đã đổi `environment.yml` sang Python `>=3.11,<3.13` để khớp
`pyproject.toml`. Không hạ phiên bản chỉ vì số phiên bản mới. Frontend có
package-lock; backend vẫn dùng khoảng phiên bản, chưa có lock đầy đủ cho
production. Cấu hình Conda không đồng nhất với môi trường pip/GPU hiện tại.

Máy kiểm thử báo Node 24.18.0, Python 3.11.15, torch 2.13.0+cu130,
transformers 4.57.6, FastAPI 0.141.1. Đây là metadata cài đặt, không phải
xác nhận GPU/driver hoạt động. Chưa kiểm thử môi trường Conda mới hay Python
3.12. Cần khóa dependency theo môi trường deployment và kiểm thử GPU/model
thật trước khi kết luận ổn định production.

## Kiểm chứng

- 87 test backend liên quan API, admission limits, prompt boundary, RAG và
  hồi quy an toàn: đạt.
- 7 unit test frontend, TypeScript, ESLint: đạt.
- Build Vinext, validate artifact và 1 kiểm thử HTML render: đạt.
- `git diff --check`, kiểm chứng bundle và đối chiếu lịch sử: đạt.
- Chạy toàn bộ pytest: dừng ở collection của 7 module training/dataset vì
  Windows Application Control chặn DLL `_C` của torch và `_csv` của PyArrow.
  Không báo toàn bộ suite hoặc pipeline ML đạt.

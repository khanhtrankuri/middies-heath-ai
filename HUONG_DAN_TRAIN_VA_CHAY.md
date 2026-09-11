# Hướng dẫn huấn luyện và chạy Meddies Health AI

Tài liệu dành cho mã nguồn hiện tại của dự án, cập nhật ngày 08/09/2026.
Mỗi lệnh đều có chú thích bắt đầu bằng `#`; có thể sao chép cả chú thích vào terminal.
Việc viết tài liệu này không thực hiện tải dữ liệu, huấn luyện hoặc triển khai ứng dụng.

## 1. Chọn luồng phù hợp

| Mục tiêu | Các mục cần làm | Điều kiện |
| --- | --- | --- |
| Thử giao diện và API | 2 → 3 → 4 | Không cần GPU hoặc adapter |
| Huấn luyện Qwen3-8B | 2 → 3 → 5 → 6 → 7 | Cấu hình chính của dự án dành cho một RTX 4090 24GB |
| Kiểm tra kỹ thuật trên RTX 4060 Laptop 8GB | 2 → 3 → 5 → 8 | Chỉ chạy smoke test, không tương đương huấn luyện đầy đủ |
| Chạy tư vấn bằng mô hình thật | 9 → 10 | Có adapter, base model, CUDA và chỉ mục RAG |
| Kiểm tra hoặc xử lý lỗi | 11 → 12 | Chọn lệnh theo vấn đề gặp phải |

Ba phần độc lập cần phân biệt:

- **Frontend**: giao diện React, chạy bằng Node.js.
- **Backend và mô hình**: FastAPI nhận yêu cầu; Qwen3-8B cùng LoRA adapter sinh câu trả lời. Chế độ `stub` chỉ trả lời mẫu.
- **RAG**: BGE-M3 tìm thông tin trong kho tài liệu bằng chỉ mục FAISS. Dữ liệu dùng để train không tự trở thành nguồn tham khảo.

Huấn luyện tạo ra **adapter**, không tự tạo chỉ mục RAG. Đổi tài liệu RAG không bắt buộc train lại.

## 2. Quy ước terminal và yêu cầu

### 2.1. Windows và PowerShell

Các mục chính dùng **PowerShell**, với đường dẫn của máy hiện tại. Nếu chuyển dự án, thay đường dẫn này bằng vị trí mới.
Lệnh nhiều dòng của PowerShell dùng dấu backtick ở cuối dòng; không thêm dấu cách hoặc chú thích sau dấu đó.
Các dòng bắt đầu bằng `--` là tham số của lệnh phía trên, không chạy riêng.

```powershell
# Đặt đường dẫn gốc của dự án cho terminal hiện tại.
$projectRoot = "C:\Users\Lenovo\Documents\meddies-health-ai"

# Chuyển về thư mục có package.json và README.md.
Set-Location $projectRoot

# Kiểm tra Node.js; package.json yêu cầu phiên bản từ 22.13.0 trở lên.
node --version

# Kiểm tra npm; dùng npm.cmd để tránh lỗi thực thi npm.ps1 trên PowerShell.
npm.cmd --version

# Kiểm tra Conda nếu chọn phương án tạo môi trường mới ở mục 3.2.
conda --version
```

Mỗi terminal mới có môi trường riêng: cần đặt lại `$projectRoot`, kích hoạt Python và khai báo biến môi trường nếu mục đó yêu cầu.

### 2.2. Máy dùng để train

Cấu hình chính trong repository là Qwen3-8B, QLoRA NF4 4-bit, BF16, một RTX 4090 24GB,
sequence length 4096, batch size 1 và gradient accumulation 16. Dự án định hướng train trên Linux hoặc WSL2;
các lệnh PowerShell dưới đây cũng phản ánh CLI hiện có, nhưng khả năng chạy phụ thuộc bộ CUDA/PyTorch/bitsandbytes của máy.

Chuẩn bị Python 3.11 hoặc 3.12; `pyproject.toml` yêu cầu `>=3.11,<3.13`. Theo hướng dẫn hiện có của dự án,
RAM nên từ 32GB, ưu tiên 64GB. Cần chỗ trống cho base model, dataset, cache và checkpoint;
đây không phải luồng chỉ tải vài MB. Không chạy server Qwen và training cùng lúc trên cùng GPU.

Nếu dùng WSL2, tạo môi trường Python **bên trong WSL**, không dùng lại `.venv-4060\Scripts\python.exe` của Windows.
Thiết lập GPU theo [hướng dẫn CUDA trên WSL của NVIDIA](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).
Cách chuyển lệnh sang Bash nằm ở mục 13.

## 3. Cài thư viện và chọn môi trường Python

### 3.1. Frontend — chạy từ thư mục gốc

```powershell
# Về thư mục gốc trước khi dùng các lệnh npm của dự án.
Set-Location $projectRoot

# Cài đúng các phiên bản frontend trong package-lock.json; cần mạng nếu chưa có cache.
npm.cmd ci
```

Nếu `node_modules` đang hoạt động và lockfile không thay đổi, không cần cài lại mỗi lần chạy.

### 3.2. Phương án A: tạo môi trường Conda mới

Chỉ chọn một phương án A hoặc B. File `backend/environment.yml` có sẵn cấu hình Python 3.11,
PyTorch/CUDA và cài backend ở chế độ editable cùng nhóm thư viện kiểm thử.

```powershell
# Đứng tại backend để mục cài editable "." trong environment.yml trỏ đúng nơi.
Set-Location "$projectRoot\backend"

# Tạo môi trường meddies-health-ai; chỉ chạy lần đầu, không chạy lại nếu môi trường đã tồn tại.
conda env create -f environment.yml

# Kích hoạt môi trường vừa tạo trong terminal này.
conda activate meddies-health-ai

# In đường dẫn Python đang dùng để phát hiện chọn nhầm môi trường.
python -c "import sys; print(sys.executable)"

# Kiểm tra các phụ thuộc Python có xung đột phiên bản hay không.
python -m pip check
```

Nếu Conda báo đã tồn tại môi trường, dùng lệnh `conda activate` ở trên, không xóa môi trường đang dùng.
Nếu chưa nhận lệnh `conda activate`, mở terminal đã được Conda cấu hình, chẳng hạn Anaconda PowerShell Prompt.

### 3.3. Phương án B: dùng môi trường `.venv-4060` có sẵn trên máy này

Đây là môi trường cục bộ, được Git bỏ qua; bản clone mới không tự có thư mục này.

```powershell
# Về gốc dự án để kiểm tra môi trường cục bộ.
Set-Location $projectRoot

# Kết quả phải là True; nếu False, dùng phương án A hoặc môi trường Python của bạn.
Test-Path ".venv-4060\Scripts\python.exe"

# Gán đường dẫn Python cho terminal này; không cần chạy script Activate.ps1.
$pythonExe = Join-Path $projectRoot ".venv-4060\Scripts\python.exe"

# Kiểm tra phiên bản và vị trí Python trong môi trường cục bộ.
& $pythonExe -c "import sys; print(sys.version); print(sys.executable)"

# Cài/cập nhật backend editable cùng thư viện kiểm thử nếu môi trường chưa có đầy đủ.
& $pythonExe -m pip install -e "./backend[dev]"

# Yêu cầu lệnh npm khởi động backend dùng đúng interpreter này.
$env:MEDDIES_PYTHON = $pythonExe
```

**Trong các mục tiếp theo, lệnh `python ...` giả định đã kích hoạt Conda.**
Nếu chọn phương án B, thay tiền tố `python` bằng `& $pythonExe`, giữ nguyên các tham số còn lại.
Ví dụ hai lệnh tương đương:

```powershell
# Dùng Python của môi trường Conda đang kích hoạt.
python -m pip check

# Hoặc dùng trực tiếp Python cục bộ; chỉ cần chạy một trong hai lệnh.
& $pythonExe -m pip check
```

### 3.4. Tạo file cấu hình mà không ghi đè file đang có

```powershell
# Về gốc để tạo cấu hình cho cả frontend và backend.
Set-Location $projectRoot

# Tạo cấu hình frontend chỉ khi chưa có; giữ nguyên cấu hình cá nhân nếu đã tồn tại.
if (-not (Test-Path ".env.local")) { Copy-Item ".env.example" ".env.local" }

# Tạo cấu hình backend chỉ khi chưa có.
if (-not (Test-Path "backend\.env")) { Copy-Item "backend\.env.example" "backend\.env" }
```

`backend:win` tự nạp `backend/.env`; `backend:demo` cũng nạp file này nhưng bắt buộc dùng `stub` và tắt RAG.
Biến đã đặt trong terminal có thể ưu tiên hơn giá trị trong `.env`. Các script training, ingestion, search và evaluation
**không tự đọc file `.env`**: chúng dùng YAML, tham số CLI và biến môi trường hiện tại.

## 4. Chạy demo trước khi train

Demo không tải Qwen hay chạy BGE-M3. Tuy nhiên môi trường Python vẫn cần các phụ thuộc backend ở mục 3.
Mở hai terminal riêng và giữ cả hai chạy.

### Terminal 1: backend demo

```powershell
# Chuyển tới gốc dự án trong terminal thứ nhất.
Set-Location "C:\Users\Lenovo\Documents\meddies-health-ai"

# Chọn môi trường backend; bỏ dòng này nếu dùng MEDDIES_PYTHON ở phương án B.
conda activate meddies-health-ai

# Chạy FastAPI tại 127.0.0.1:8000 với phản hồi mẫu, không cần GPU.
npm.cmd run backend:demo
```

Chờ thông báo `Application startup complete`. Lệnh này giữ terminal bận để phục vụ API.

### Terminal 2: giao diện

```powershell
# Chuyển tới gốc dự án trong terminal thứ hai.
Set-Location "C:\Users\Lenovo\Documents\meddies-health-ai"

# Khởi động Vite; mở đúng địa chỉ Local in ra, mặc định thường là http://localhost:5173/.
npm.cmd run dev:win
```

Mở trang, gửi mô tả triệu chứng, trả lời thời gian, thử tạo cuộc trò chuyện mới.
Phản hồi demo chỉ kiểm tra luồng ứng dụng, không phải kết quả từ mô hình đã train.
Dừng từng dịch vụ bằng **Ctrl+C** tại terminal tương ứng.

### Terminal 3: kiểm tra kết nối

```powershell
# Kiểm tra backend có nhận HTTP hay không.
Invoke-RestMethod "http://127.0.0.1:8000/health"

# Kiểm tra trạng thái; demo dự kiến api=True, model=True, rag=False.
Invoke-RestMethod "http://127.0.0.1:8000/ready"

# Chuyển về gốc để gọi script smoke test.
Set-Location "C:\Users\Lenovo\Documents\meddies-health-ai"

# Kiểm tra frontend, CORS, hỏi bổ sung, kết quả demo, cảnh báo khẩn cấp và validation.
# Script này yêu cầu frontend ở localhost:5173 và backend demo ở 127.0.0.1:8000.
npm.cmd run smoke:local
```

`model=True` trong demo có nghĩa provider mẫu đã nạp, **không có nghĩa Qwen đang chạy**.

## 5. Kiểm tra GPU trước khi huấn luyện

Dừng backend dùng mô hình thật trước bước này. Mở terminal đã kích hoạt môi trường Python.

```powershell
# Chuyển tới backend; các đường dẫn data/, models/ và training/ sau đây tính từ đây.
Set-Location "$projectRoot\backend"

# Xem GPU, driver và bộ nhớ đang bị các tiến trình khác sử dụng.
nvidia-smi

# Chỉ cho tiến trình Python nhìn thấy GPU số 0; dự án yêu cầu đúng một GPU hiển thị.
$env:CUDA_VISIBLE_DEVICES = "0"

# Hiển thị phiên bản Torch, CUDA của Torch và khả năng truy cập GPU.
python -c "import torch; print('Torch:', torch.__version__); print('CUDA build:', torch.version.cuda); print('CUDA available:', torch.cuda.is_available()); print('Visible GPUs:', torch.cuda.device_count())"

# Kiểm tra tên GPU, VRAM và BF16; dừng ngay nếu Torch chưa sử dụng được CUDA.
python -c "import torch; assert torch.cuda.is_available(), 'CUDA unavailable'; p=torch.cuda.get_device_properties(0); print(p.name); print('VRAM GiB:', round(p.total_memory/1024**3, 2)); print('BF16:', torch.cuda.is_bf16_supported())"
```

Chỉ tiếp tục train khi CUDA hoạt động và GPU phù hợp. Nếu Torch đang là bản CPU,
chọn OS/Pip/Python/CUDA tương ứng ở [bộ chọn cài đặt chính thức của PyTorch](https://pytorch.org/get-started/locally/),
cài vào **đúng interpreter đang dùng**, rồi chạy lại kiểm tra trên. Không mặc định một wheel CUDA phù hợp mọi driver.

## 6. Chuẩn bị dataset

Thực hiện từ `backend/`, đã kích hoạt Python. Script dùng dataset `Meddies/meddies-consultant`.
Đây là dataset tổng hợp; theo tài liệu dự án, giấy phép là CC BY-NC 4.0. Cần kiểm tra quyền sử dụng
cho mục đích của bạn; không lấy các hàng QA làm nguồn y khoa trong RAG.

```powershell
# Xem hai mẫu tiếng Việt bằng streaming; không materialize toàn bộ dataset để xem mẫu.
python scripts/preview_dataset.py --config vietnamese --limit 2

# Làm sạch dữ liệu tiếng Việt và tiếng Anh, bỏ phần think, loại bản ghi lỗi/trùng,
# rồi chia train/validation theo seed cố định vào data/processed.
python -m training.data.prepare_meddies `
  --configs vietnamese english `
  --output-dir data/processed `
  --seed 42 `
  --validation-ratio 0.05

# Xem số mẫu hợp lệ, lỗi và trùng đã xử lý của từng ngôn ngữ.
Get-Content "data/processed/metadata.json" -Encoding utf8

# Kiểm tra các file train và validation đã được tạo.
Get-ChildItem "data/processed" -Recurse -Filter "*.jsonl"
```

| Tham số | Ý nghĩa |
| --- | --- |
| `--configs vietnamese english` | Chuẩn bị hai nhóm dữ liệu mà cấu hình Stage 1 sử dụng |
| `--output-dir data/processed` | Khớp `data.processed_dir` trong YAML RTX 4090 |
| `--seed 42` | Giữ cách chia xác định cho cùng nội dung và tham số |
| `--validation-ratio 0.05` | Tỷ lệ mục tiêu 5% cho validation; số lượng thực tế có thể lệch do cách chia bằng hash |
| `--max-samples N` | Tùy chọn giới hạn số hàng đọc **mỗi config**, trước khi lọc lỗi và trùng |

Kết quả chính là `data/processed/vietnamese/train.jsonl`, `validation.jsonl` và các file tương tự dưới `english/`.
Script hiện tạo **train và validation**, chưa tạo tập test độc lập. Chạy lại cùng thư mục sẽ ghi lại các file đó;
không chạy chuẩn bị dữ liệu cùng lúc với một tiến trình train đang đọc chúng.

## 7. Huấn luyện chính trên RTX 4090 24GB

### 7.1. Chạy thử ba bước trước khi train đầy đủ

Đứng tại `backend/`, giữ `CUDA_VISIBLE_DEVICES=0`. Lần đầu cần tải tokenizer và base model nếu chưa có cache.

```powershell
# Đọc cấu hình chính để biết thông số đang áp dụng trước khi dùng GPU.
Get-Content "training/configs/stage1_qwen3_8b_4090.yaml" -Encoding utf8

# Chạy ba optimizer step với tối đa 100 mẫu train và 30 mẫu validation.
# Dùng output riêng để không ghi đè adapter của lần train đầy đủ.
python -m training.train_stage1 `
  --config training/configs/stage1_qwen3_8b_4090.yaml `
  --max-train-samples 100 `
  --max-eval-samples 30 `
  --output-dir models/stage1_smoke_4090 `
  --smoke-test

# Xem cấu hình và metrics được lưu khi toàn bộ smoke test hoàn tất.
Get-Content "models/stage1_smoke_4090/run_metadata/run.json" -Encoding utf8
```

`--smoke-test` thực hiện train, evaluate, lưu adapter, nạp lại adapter và sinh thử một câu trả lời.
Mẫu thực tế có thể ít hơn giới hạn nếu dữ liệu không đủ. Adapter nằm tại
`models/stage1_smoke_4090/final_adapter/`; nó chỉ dùng để xác nhận luồng kỹ thuật.

### 7.2. Chạy Stage 1 đầy đủ

Chỉ chạy sau khi smoke test thành công. Đây là lệnh tốn thời gian và tài nguyên thực sự.

```powershell
# Train toàn bộ dữ liệu đã chuẩn bị với cấu hình Stage 1, lưu sang thư mục sản phẩm riêng.
# Lần train mới nên dùng output-dir mới nếu models/stage1_consult đã chứa kết quả cần giữ.
python -m training.train_stage1 `
  --config training/configs/stage1_qwen3_8b_4090.yaml `
  --output-dir models/stage1_consult
```

| Cấu hình mặc định | Giá trị / ý nghĩa |
| --- | --- |
| Base model | `Qwen/Qwen3-8B` |
| Quantization | NF4 4-bit, double quantization, BF16 compute |
| LoRA | Rank 32, alpha 64, dropout 0.05 |
| Dữ liệu trộn | 65% tiếng Việt, 35% tiếng Anh |
| Sequence length | 4096 token |
| Batch / accumulation | 1 mẫu mỗi bước vi mô, tích lũy 16 bước; effective batch 16 |
| Learning rate / epochs | `1e-4` / 1 epoch |
| Checkpoint / evaluation | Mỗi 250 bước, giữ tối đa 3 checkpoint |
| Packing | Tắt mặc định |

Base weights được giữ cố định; quá trình học cập nhật LoRA. Không cần merge base model để chạy backend mặc định.

```powershell
# Chạy ở terminal khác để xem bộ nhớ và mức sử dụng GPU mỗi hai giây; Ctrl+C để dừng theo dõi.
nvidia-smi -l 2
```

Sau khi train hoàn tất:

```text
backend/models/stage1_consult/
  checkpoint-.../          # Checkpoint giữa chừng nếu đã tới mốc lưu
  final_adapter/          # Adapter và tokenizer cuối cùng
  run_metadata/run.json   # Cấu hình, metrics và số liệu bộ nhớ của lần chạy
```

### 7.3. Tiếp tục từ checkpoint

```powershell
# Liệt kê checkpoint thực sự tồn tại; lấy đúng tên thư mục từ kết quả này.
Get-ChildItem "models/stage1_consult" -Directory -Filter "checkpoint-*"

# Ví dụ tiếp tục checkpoint-1000: thay bằng checkpoint có thật của bạn trước khi chạy.
# Giữ cấu hình, dữ liệu và output-dir của lần train đã tạo checkpoint đó.
python -m training.train_stage1 `
  --config training/configs/stage1_qwen3_8b_4090.yaml `
  --output-dir models/stage1_consult `
  --resume-from-checkpoint models/stage1_consult/checkpoint-1000
```

`final_adapter/` dùng để suy luận hoặc khởi tạo Stage 2; không thay thế checkpoint chứa trạng thái optimizer khi resume.
Nếu bị ngắt trước khi tới mốc lưu, có thể chưa có checkpoint để tiếp tục.

### 7.4. Sinh câu trả lời để đánh giá adapter

```powershell
# Nạp base model và adapter, chạy ba prompt mẫu Việt/Anh và lưu kết quả JSON để đọc lại.
python -m training.evaluate_consultation `
  --checkpoint models/stage1_consult/final_adapter `
  --output models/stage1_consult/evaluation.json

# Đọc các câu trả lời đã sinh để kiểm tra hành vi hỏi bổ sung và mức độ phù hợp.
Get-Content "models/stage1_consult/evaluation.json" -Encoding utf8
```

Script này kiểm tra hành vi cơ bản trên ba prompt, không chạy toàn bộ API/RAG, không tính độ chính xác chẩn đoán,
và không thay thế một bộ đánh giá độc lập cùng rà soát chuyên môn. Loss thấp hoặc smoke test đạt chưa đủ để dùng trong thực tế.

## 8. Nhánh riêng: smoke test trên RTX 4060 Laptop 8GB

Chỉ dùng để kiểm tra đường đi train → lưu → nạp → sinh câu trả lời. Cấu hình giảm xuống sequence length 256,
LoRA rank 4, batch 1 và không tạo DataLoader subprocess. Không dùng YAML RTX 4090 mặc định để giả định rằng 8GB sẽ đủ.
Kết quả cũ trên máy này được ghi trong [RTX4060_8GB_SMOKE.md](backend/training/RTX4060_8GB_SMOKE.md);
đó không phải cam kết về bộ nhớ hoặc chất lượng trên mọi lần chạy.

Đứng tại `backend/`, dùng môi trường Python có CUDA theo mục 3 và 5.

```powershell
# Chỉ cho tiến trình nhìn thấy một GPU.
$env:CUDA_VISIBLE_DEVICES = "0"

# Chuẩn bị tối đa 200 hàng mỗi ngôn ngữ vào thư mục riêng của cấu hình 4060.
# Không ghi đè dataset đầy đủ ở data/processed.
python -m training.data.prepare_meddies `
  --configs vietnamese english `
  --output-dir data/processed_4060_smoke `
  --seed 42 `
  --max-samples 200

# Chạy ba optimizer step; dùng thư mục riêng để giữ adapter debug đã có trên máy.
python -m training.train_stage1 `
  --config training/configs/stage1_qwen3_8b_4060_8gb_smoke.yaml `
  --max-train-samples 16 `
  --max-eval-samples 4 `
  --output-dir models/debug_4060_8gb_manual `
  --smoke-test

# Đọc metrics sau khi smoke test hoàn tất.
Get-Content "models/debug_4060_8gb_manual/run_metadata/run.json" -Encoding utf8
```

Adapter của nhánh này nằm ở `models/debug_4060_8gb_manual/final_adapter/`.
Không thay nó vào đường dẫn adapter sản xuất và coi như mô hình đã được huấn luyện đầy đủ.
Trên Windows WDDM, số peak của PyTorch có thể gồm bộ nhớ chia sẻ/ảo; hãy đọc cùng số liệu `nvidia-smi`
và lưu ý giới hạn đã ghi trong báo cáo diagnostic của dự án.

## 9. Chuẩn bị kho tài liệu RAG

Đứng tại `backend/`. Chuẩn bị tài liệu đã được kiểm duyệt và có quyền sử dụng phù hợp.
Đầu vào hỗ trợ TXT, Markdown, JSON, HTML và PDF có lớp văn bản; loader hiện không OCR PDF scan.
Không lấy dữ liệu Meddies/RandomQA hoặc fixture trong `backend/tests/fixtures/` làm kho tài liệu cho người dùng thật.

### 9.1. Đặt tài liệu và metadata

```powershell
# Tạo thư mục chỉ chứa tài liệu đã duyệt; giữ README hướng dẫn ở ngoài thư mục được index.
New-Item -ItemType Directory -Path "data/knowledge/reviewed" -Force
```

Đặt các file của bạn vào thư mục vừa tạo, chẳng hạn `tai-lieu.md` và sidecar `tai-lieu.md.metadata.json`.
Loader đọc đệ quy các file được hỗ trợ: vì vậy không đặt README hướng dẫn, ví dụ giả hoặc ghi chú phát triển trong thư mục index.
Ví dụ cấu trúc metadata dưới đây chỉ là **mẫu định dạng**, cần thay thông tin bằng dữ liệu từ tài liệu thực:

```json
{
  "source_id": "ma-tai-lieu-da-duyet-001",
  "title": "Tên thật của tài liệu",
  "organization": "Đơn vị thực sự phát hành",
  "source_url": null,
  "publication_date": null,
  "jurisdiction": "VN",
  "language": "vi"
}
```

Thông tin không biết để `null` hoặc bỏ trường, không đoán ngày, tổ chức hoặc URL.
Xem thêm [schema tài liệu RAG](backend/data/knowledge/README.md).

### 9.2. Tạo chỉ mục

```powershell
# Xem những file sẽ được index; chỉ chạy bước sau khi đã có tài liệu thực sự được duyệt.
Get-ChildItem "data/knowledge/reviewed" -Recurse -File

# Tạo FAISS index bằng BGE-M3 trên CPU, chia đoạn 700 ký tự với chồng lấn 100 ký tự.
# Lần đầu có thể tải BGE-M3; CPU embeddings giữ VRAM cho Qwen.
# --rebuild cho phép thay thế chỉ mục cũ tại đúng output-dir này.
python scripts/ingest_knowledge.py `
  --input-dir data/knowledge/reviewed `
  --output-dir data/rag_index `
  --embedding-model BAAI/bge-m3 `
  --device cpu `
  --batch-size 16 `
  --chunk-size 700 `
  --chunk-overlap 100 `
  --rebuild

# Kiểm tra các file chỉ mục và thống kê được tạo.
Get-ChildItem "data/rag_index"
```

Đầu ra gồm `vectors.faiss`, `chunks.jsonl`, `metadata.json`, `manifest.json`.
`--batch-size` ở đây là số đoạn đưa qua embedding mỗi lượt, khác batch size training.
Dừng backend khi thay chỉ mục đang phục vụ, rồi khởi động lại để nạp bản mới.

### 9.3. Tìm thử và đánh giá retrieval

```powershell
# Bật RAG cho các script CLI; chúng không tự nạp backend/.env.
$env:MEDDIES_RAG_ENABLED = "true"

# Chọn chỉ mục vừa xây; đường dẫn tương đối được RAG tính từ backend.
$env:MEDDIES_RAG_INDEX_PATH = "data/rag_index"

# Dùng đúng embedding model đã dùng khi tạo chỉ mục.
$env:MEDDIES_EMBEDDING_MODEL = "BAAI/bge-m3"

# Đặt embedding trên CPU như cấu hình ingestion phía trên.
$env:MEDDIES_EMBEDDING_DEVICE = "cpu"

# Tìm năm đoạn tham khảo; thay câu hỏi bằng chủ đề có trong kho của bạn khi cần.
python scripts/search_knowledge.py --query "Migraine là gì?" --top-k 5

# Mở bộ câu hỏi đánh giá để chỉnh expected_source_ids khớp source_id thực tế của kho.
notepad "evals/rag_cases.yaml"

# Chỉ chạy sau khi các case đã được đối chiếu; in Recall@K, MRR và source-hit rate.
python evals/evaluate_rag.py --cases evals/rag_cases.yaml
```

Các source ID trong file case có sẵn là ví dụ cần đáp ứng hoặc sửa lại theo kho thực tế.
Không đổi nhãn kỳ vọng chỉ để làm điểm tăng. Chỉ số retrieval không chứng minh câu trả lời đúng về lâm sàng.

## 10. Chạy project với AI thật

### 10.1. Điều kiện cần có

- Adapter từ một lần train đầy đủ, hoặc adapter phù hợp đã có: ví dụ `backend/models/stage1_consult/final_adapter/`.
- Base model `Qwen/Qwen3-8B` có trong cache hoặc tải được; chỉ có adapter là chưa đủ.
- Chỉ mục RAG dùng đúng embedding model; backend có thể chạy suy giảm khi RAG thiếu, nhưng đó chưa phải luồng có nguồn đầy đủ.
- Python/CUDA hoạt động, GPU không đang bị tiến trình training chiếm dụng.

### 10.2. Chỉnh cấu hình

```powershell
# Mở cấu hình backend đã tạo ở mục 3.4.
notepad "$projectRoot\backend\.env"

# Mở cấu hình frontend để xác nhận URL gọi tới API.
notepad "$projectRoot\.env.local"
```

Các giá trị chính trong `backend/.env` — mỗi dòng có chú thích riêng:

```dotenv
# Dùng mô hình Transformers thật; stub chỉ dùng cho kiểm thử.
MEDDIES_MODEL_PROVIDER=transformers
# Base model phải phù hợp với adapter.
MEDDIES_BASE_MODEL=Qwen/Qwen3-8B
# Đường dẫn adapter tính từ backend khi dùng launcher của dự án.
MEDDIES_MODEL_PATH=models/stage1_consult/final_adapter
# Bật truy xuất tài liệu đã duyệt.
MEDDIES_RAG_ENABLED=true
# Thư mục FAISS đã tạo ở mục 9.
MEDDIES_RAG_INDEX_PATH=data/rag_index
# Phải khớp model dùng để tạo embeddings cho chỉ mục.
MEDDIES_EMBEDDING_MODEL=BAAI/bge-m3
# Giữ embedding trên CPU để dành GPU cho Qwen.
MEDDIES_EMBEDDING_DEVICE=cpu
# Lấy tối đa 8 ứng viên trước khi chọn nguồn cuối.
MEDDIES_RAG_TOP_K=8
# Chọn tối đa 4 đoạn để đưa vào ngữ cảnh, còn phụ thuộc ngân sách token.
MEDDIES_RAG_FINAL_K=4
# Cho phép frontend local gọi API; thêm đúng origin nếu cổng hoặc host thay đổi.
MEDDIES_CORS_ORIGINS=http://localhost:3000,http://localhost:5173
# Giới hạn một tác vụ sinh câu trả lời cùng lúc trên GPU.
MEDDIES_MAX_GENERATIONS=1
# Giới hạn độ dài câu trả lời sinh ra, không phải độ dài toàn bộ ngữ cảnh.
MEDDIES_MAX_NEW_TOKENS=384
# Tắt ghi nội dung truy vấn RAG vào log theo mặc định.
MEDDIES_LOG_CONTENT=false
```

Trong `.env.local` của frontend:

```dotenv
# API đang chạy trên cùng máy với trình duyệt.
NEXT_PUBLIC_MEDDIES_API_URL=http://localhost:8000
```

Giữ các thông số còn lại từ `.env.example` nếu chưa có lý do điều chỉnh.
Biến `NEXT_PUBLIC_...` nằm ở phía trình duyệt, không đặt token hoặc mật khẩu vào đó.

### 10.3. Khởi động hai dịch vụ

Terminal backend:

```powershell
# Về gốc dự án trong terminal backend.
Set-Location "C:\Users\Lenovo\Documents\meddies-health-ai"

# Chọn môi trường Python đúng; nếu dùng phương án B, đặt MEDDIES_PYTHON thay dòng này.
conda activate meddies-health-ai

# Chọn GPU duy nhất dùng để nạp mô hình.
$env:CUDA_VISIBLE_DEVICES = "0"

# Đặt rõ provider thật, tránh giá trị stub còn sót trong terminal từ lần kiểm thử trước.
$env:MEDDIES_MODEL_PROVIDER = "transformers"

# Bật rõ RAG, tránh biến tắt RAG từ terminal kiểm thử ghi đè file .env.
$env:MEDDIES_RAG_ENABLED = "true"

# Nạp backend/.env và khởi động FastAPI; chờ mô hình và chỉ mục nạp xong.
npm.cmd run backend:win
```

Terminal frontend:

```powershell
# Về gốc dự án trong terminal giao diện.
Set-Location "C:\Users\Lenovo\Documents\meddies-health-ai"

# Khởi động frontend; nếu vừa đổi .env.local, cần dừng và chạy lại lệnh này.
npm.cmd run dev:win
```

Terminal kiểm tra:

```powershell
# Chờ server sẵn sàng rồi đọc trạng thái; mục tiêu cho luồng đầy đủ là cả ba giá trị True.
Invoke-RestMethod "http://127.0.0.1:8000/ready"

# Mở tài liệu API tương tác, nơi có thể thử POST /api/v1/consultation.
Start-Process "http://127.0.0.1:8000/docs"
```

`/health` chỉ xác nhận API sống; `/ready` phân biệt API, provider mô hình và RAG.
Các cờ readiness không đánh giá chất lượng tư vấn. Trong phản hồi API, `provider` phải là `transformers`
cho lượt sinh bởi Qwen; `safety-router` là bình thường với nhánh khẩn cấp.

### 10.4. Chạy frontend từ bản build

Backend vẫn cần chạy ở terminal riêng. Dừng frontend development trước để tránh nhầm địa chỉ.

```powershell
# Về gốc dự án để đóng gói giao diện.
Set-Location $projectRoot

# Build frontend từ source và cấu hình môi trường hiện tại.
npm.cmd run build:win

# Xác nhận Worker, manifest Sites và ảnh chia sẻ có trong artifact.
npm.cmd run validate:artifact:win

# Phục vụ frontend đã build; mở đúng URL được lệnh in ra.
npm.cmd run start:win
```

Build frontend không đóng gói Python, GPU, model weights hoặc kho FAISS vào website.
Để chạy trực tuyến, backend phải được vận hành riêng; đổi URL frontend sang API HTTPS truy cập được,
thêm đúng origin vào CORS và build lại. Các lệnh trên chưa xuất bản lên Sites hay thay đổi website đang hoạt động.

## 11. Kiểm tra mã nguồn và lưu thông tin môi trường

Chạy kiểm thử Python trong terminal riêng để các biến `stub` không ảnh hưởng terminal phục vụ AI thật.

```powershell
# Về thư mục backend trong terminal kiểm thử đã chọn đúng Python.
Set-Location "$projectRoot\backend"

# Bắt buộc dùng provider mẫu trong unit test, không nạp Qwen.
$env:MEDDIES_MODEL_PROVIDER = "stub"

# Tắt RAG thực để unit test không nạp BGE-M3 hoặc chỉ mục sản xuất.
$env:MEDDIES_RAG_ENABLED = "false"

# Chạy các bài kiểm thử API, RAG, inference và xử lý dữ liệu training.
python -m pytest

# Về gốc để chạy chuỗi kiểm tra frontend dành cho Windows.
Set-Location $projectRoot

# Chạy TypeScript, lint, unit test, build, kiểm tra artifact và HTML render từ Worker.
npm.cmd run test:win
```

Sau khi thiết lập được môi trường chạy tốt, có thể lưu danh sách thư viện cùng kết quả của lần train:

```powershell
# Về backend để ghi tệp cạnh metrics của lần train đã hoàn tất.
Set-Location "$projectRoot\backend"

# Lưu phiên bản các gói; chỉ chạy khi thư mục run_metadata của lần train này đã tồn tại.
# pip freeze là bản ghi môi trường, không phải bảo đảm tái lập CUDA/driver giữa các máy.
python -m pip freeze | Out-File "models/stage1_consult/run_metadata/pip-freeze.txt" -Encoding utf8
```

## 12. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
| --- | --- |
| `npm.ps1 cannot be loaded` | Dùng `npm.cmd`; không cần đổi execution policy toàn máy |
| `No module named app` hoặc `training` | Đứng tại `backend/`, dùng đúng Python và cài editable theo mục 3 |
| `No module named uvicorn` | Backend chưa được cài vào interpreter mà launcher chọn; kiểm tra `MEDDIES_PYTHON` |
| `torch.cuda.is_available()` là `False` | Kiểm tra driver bằng `nvidia-smi`, đúng môi trường và wheel Torch hỗ trợ CUDA |
| Yêu cầu đúng một GPU nhưng phát hiện nhiều GPU | Đặt `CUDA_VISIBLE_DEVICES=0` trước khi khởi động Python |
| Không tìm thấy adapter | Kiểm tra `MEDDIES_MODEL_PATH`; phải trỏ thư mục `final_adapter` tồn tại, không trỏ mỗi base model |
| `rag=False` | Xem đường dẫn chỉ mục, embedding model, log khởi động và kết quả search ở mục 9 |
| Không tìm thấy tài liệu để index | Thêm tài liệu thực vào `data/knowledge/reviewed`; thư mục rỗng không tạo được index |
| Train báo dữ liệu rỗng | Đọc `metadata.json`, tăng số mẫu chuẩn bị và kiểm tra cả train/validation của từng config |
| Trình duyệt không gọi được API nhưng `/health` truy cập được | Kiểm tra URL frontend và CORS; `localhost` khác `127.0.0.1`, cổng cũng là một phần origin |
| Frontend tự chuyển sang 5174 | Cổng 5173 đang bị dùng; thêm origin mới vào CORS hoặc dừng dịch vụ cũ do bạn mở. Smoke script mặc định chỉ dùng 5173 |
| Câu trả lời có nhãn kiểm thử | Đang dùng `stub`; dừng backend:demo và chạy backend:win với cấu hình thật |
| `grounding_status=degraded` dù API vẫn chạy | RAG chưa dùng được hoặc mô hình chưa dẫn nguồn hợp lệ; readiness không bảo đảm mọi câu trả lời có trích dẫn |
| Giao diện hết thời gian chờ sau 90 giây | Kiểm tra GPU/độ dài sinh và tải server; gửi lại có thể phải đợi tác vụ GPU cũ hoàn tất |

### 12.1. Thiếu VRAM trên cấu hình 4090

Theo thứ tự fallback trong mã nguồn: giữ batch 1 và gradient checkpointing, giảm sequence length
4096 → 3072 → 2048, rồi giảm LoRA rank 32 → 16 nếu vẫn thiếu. Gradient accumulation quyết định effective batch;
giảm sequence length hoặc rank không tự làm thay đổi số mẫu của effective batch.

```powershell
# Chạy smoke test với sequence length 3072 ở output riêng để thử mức bộ nhớ thấp hơn.
python -m training.train_stage1 `
  --config training/configs/stage1_qwen3_8b_4090.yaml `
  --max-seq-length 3072 `
  --max-train-samples 100 `
  --max-eval-samples 30 `
  --output-dir models/stage1_smoke_3072 `
  --smoke-test

# Nếu optimizer bitsandbytes không tương thích, thử optimizer Torch bằng một smoke run riêng.
# Đây là phương án xử lý lỗi optimizer, không phải cam kết giảm bộ nhớ.
python -m training.train_stage1 `
  --config training/configs/stage1_qwen3_8b_4090.yaml `
  --optim adamw_torch `
  --max-train-samples 100 `
  --max-eval-samples 30 `
  --output-dir models/stage1_smoke_adamw `
  --smoke-test
```

Nếu đổi kiến trúc LoRA/rank, bắt đầu một lần train mới; không dùng tùy tiện checkpoint cũ không tương thích.
Các lệnh này không biến cấu hình train đầy đủ thành cấu hình thích hợp cho RTX 4060 8GB.

## 13. Linux / WSL2: cách chuyển các lệnh

Dùng môi trường Linux riêng, Node.js và Conda bên trong Linux. Với WSL, ví dụ dưới truy cập source Windows qua `/mnt/c/`;
nếu dùng bản sao trong filesystem Linux, thay đường dẫn tương ứng. Không dùng chung `node_modules` đã cài trên Windows
cho tiến trình Node Linux; dùng checkout riêng nếu cần chạy frontend ở cả hai hệ điều hành.

```bash
# Chuyển tới backend của dự án; thay đường dẫn nếu checkout ở vị trí khác.
cd /mnt/c/Users/Lenovo/Documents/meddies-health-ai/backend

# Chỉ tạo lần đầu, dùng Conda đã cài bên trong Linux/WSL.
conda env create -f environment.yml

# Kích hoạt môi trường Linux cho các lệnh Python tiếp theo.
conda activate meddies-health-ai

# Xác nhận Torch trong WSL nhìn thấy GPU trước khi train.
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"

# Chuẩn bị dataset bằng cùng CLI với Windows.
python -m training.data.prepare_meddies --configs vietnamese english --output-dir data/processed --seed 42

# Chạy smoke test; Bash dùng dấu gạch chéo ngược để nối dòng và phép gán env trước lệnh.
CUDA_VISIBLE_DEVICES=0 python -m training.train_stage1 \
  --config training/configs/stage1_qwen3_8b_4090.yaml \
  --max-train-samples 100 \
  --max-eval-samples 30 \
  --output-dir models/stage1_smoke_4090 \
  --smoke-test

# Sau khi có adapter và RAG theo các mục trên, nạp .env rõ ràng khi chạy trực tiếp Uvicorn.
# Đặt provider/RAG trước lệnh để không kế thừa chế độ demo; lệnh này giữ terminal để phục vụ API.
CUDA_VISIBLE_DEVICES=0 MEDDIES_MODEL_PROVIDER=transformers MEDDIES_RAG_ENABLED=true \
  python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

Các tham số của script Python giống nhau trên hai hệ điều hành. Trong Bash, thay `$env:TEN="gia-tri"`
bằng `export TEN="gia-tri"`, `Get-Content` bằng `cat`, `Set-Location` bằng `cd`, và `npm.cmd` bằng `npm`.
Nếu frontend vẫn chạy trên Windows còn backend trong WSL, kiểm tra khả năng truy cập API từ Windows trước,
không chỉ kiểm tra `/health` bên trong WSL.

## 14. Tùy chọn nâng cao: Stage 2 và merge

### 14.1. Stage 2 — chỉ thử khi cần và đánh giá có cải thiện

Stage 2 trong mã nguồn là bước mixed replay với 60% RandomQA, 30% hội thoại Việt và 10% hội thoại Anh.
Nó không bắt buộc để khởi động web. Đứng tại `backend/` trong môi trường CUDA phù hợp.

```powershell
# Chuẩn bị riêng config RandomQA còn thiếu; giữ nguyên hai config hội thoại đã chuẩn bị.
python -m training.data.prepare_meddies --configs RandomQA --output-dir data/processed --seed 42

# Tiếp tục huấn luyện từ adapter Stage 1, lưu adapter kết quả sang thư mục Stage 2.
# Lệnh này train thật; muốn kiểm tra trước có thể thêm --smoke-test và output-dir riêng.
python -m training.train_stage2 `
  --config training/configs/stage2_qwen3_8b_4090.yaml `
  --stage1-adapter models/stage1_consult/final_adapter `
  --strategy continue `
  --output-dir models/stage2_consult

# Sinh cùng nhóm prompt mẫu để so sánh hành vi Stage 2 với kết quả Stage 1.
python -m training.evaluate_consultation `
  --checkpoint models/stage2_consult/final_adapter `
  --output models/stage2_consult/evaluation.json
```

Lưu ý: lệnh prepare chỉ chạy RandomQA sẽ ghi lại `data/processed/metadata.json` với thống kê lần chạy này;
các file hội thoại trong thư mục ngôn ngữ vẫn giữ nguyên. Lưu thống kê Stage 1 trước nếu cần đối chiếu.
Chỉ chuyển `MEDDIES_MODEL_PATH` sang adapter Stage 2 sau khi đánh giá cho thấy phù hợp hơn.

### 14.2. Merge adapter — không cần cho backend Transformers mặc định

```powershell
# Chỉ chạy khi thật sự cần bản model đã hợp nhất; dùng CPU và thư mục đầu ra riêng.
# Bước này cần RAM và dung lượng đĩa đáng kể, không phải giải pháp để giảm VRAM khi train.
python -m training.merge_lora `
  --base-model Qwen/Qwen3-8B `
  --adapter models/stage1_consult/final_adapter `
  --output models/stage1_consult/merged `
  --device cpu
```

Luồng phục vụ mặc định vẫn là **base model + adapter + chỉ mục RAG**.
Xem [README chính](README.md) để đọc thêm kiến trúc và [cấu hình Stage 1](backend/training/configs/stage1_qwen3_8b_4090.yaml)
khi cần thay đổi các tham số của một lần train.

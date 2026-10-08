# Meddies Health AI

Meddies Health AI là hệ thống hỗ trợ thông tin và sàng lọc sức khỏe bằng tiếng
Việt, gồm:

- giao diện React/TypeScript;
- FastAPI backend;
- Qwen3-0.6B hoặc Qwen3-1.7B với BF16 LoRA;
- hybrid RAG: BM25 + BGE-M3 + RRF + BGE reranker;
- kiểm tra dấu hiệu khẩn cấp và trích dẫn nguồn.

Đây không phải hệ thống chẩn đoán và không thay thế nhân viên y tế.

## Bắt đầu

Toàn bộ quy trình cài đặt, chuẩn bị dữ liệu, train, smoke test, đánh giá, tạo RAG
index và chạy hệ thống được giữ tại một tài liệu duy nhất:

**[Hướng dẫn train và chạy hệ thống](HUONG_DAN_TRAIN_VA_CHAY.md)**

Cấu hình giới hạn API, ranh giới tin cậy đăng nhập và kết quả kiểm tra:
**[Kiểm tra bảo mật và dependency](SECURITY_REVIEW.md)**.

Chạy nhanh giao diện và backend giả lập, không cần GPU:

```powershell
npm.cmd ci
npm.cmd run backend:demo
```

Trong terminal khác:

```powershell
npm.cmd run dev:win
```

## Kiến trúc

```text
Browser
  -> React UI
  -> FastAPI
  -> emergency/red-flag screening
  -> query builder
  -> BM25 + BGE-M3
  -> reciprocal-rank fusion
  -> BGE cross-encoder reranker
  -> context budgeting
  -> configured Qwen3 model + LoRA adapter
  -> citation validation
```

Training dùng thứ tự cấu hình:

```text
defaults -> hardware YAML -> CLI overrides
```

Hai hardware profile được duy trì:

- `backend/training/configs/rtx4090_24gb.yaml`
- `backend/training/configs/rtx4060_8gb.yaml`

Model được chọn độc lập bằng `--model-name`:

- `Qwen/Qwen3-1.7B`
- `Qwen/Qwen3-0.6B`

## Các lệnh kiểm tra

```powershell
npm.cmd run backend:test
npm.cmd run typecheck
npm.cmd run lint:win
npm.cmd run test:unit
npm.cmd run build:win
npm.cmd run validate:artifact:win
```

Các biến môi trường backend mẫu nằm tại `backend/.env.example`.

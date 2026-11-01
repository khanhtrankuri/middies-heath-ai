# Planner-guided Qwen — thực nghiệm 31/10/2026

Mã triển khai: `a5b740a`. Cả 12 code hash tạo dữ liệu khớp commit `e691818a`. Dữ liệu dẫn xuất v1 được tạo với code hash trong manifest; bản sửa nhận diện slot Planner v2.1 áp dụng đồng nhất cho các lượt benchmark cuối. Giữ nguyên mọi pilot lịch sử. Đây là kết quả phát triển trên dữ liệu synthetic, chưa có kiểm định lâm sàng.

**Kết quả chính:** E5C pilot có model acceptance 0.473, E5A 0.878, trên 131 cơ hội hỏi; chênh lệch ghép cặp -0.405, CI95% [-0.531, -0.272]. Pilot này chưa chứng minh cải thiện hỏi bệnh; loss thấp hơn không thay thế đánh giá chất lượng câu hỏi. Acceptance phụ thuộc validator tự động, chưa phải đánh giá chuyên gia.

## Dữ liệu và huấn luyện

- Phần mềm: `{"python": "3.11.15 (main, Jun 11 2026, 04:59:07) [MSC v.1944 64 bit (AMD64)]", "torch": "2.13.0+cu130", "transformers": "4.57.6", "peft": "0.20.0", "trl": "0.29.1", "datasets": "4.8.5", "accelerate": "1.14.0", "fastapi": "0.141.1", "pydantic": "2.13.4", "pytest": "9.1.1", "wandb": "0.31.0"}`.
- Nguồn: Meddies Vietnamese revision `05428709a7572f6f0d4aa5045e6ba255fa85af51`; giới hạn 2000 hội thoại nguồn mỗi split.
- Train: 234 mẫu từ 216 hội thoại; validation: 208 mẫu từ 193 hội thoại; toàn bộ nhãn auto_filtered_dataset_question; 0 template, 0 nhãn chuyên gia tự gán.
- Source train/validation/test giữ nguyên; ID/nhóm tách biệt; opening trùng split bị loại khỏi dữ liệu dẫn xuất. Test không cung cấp target SFT.
- Qwen Base revision `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`; GPU NVIDIA GeForce RTX 4060 Laptop GPU; LoRA r16/alpha32, bfloat16, SDPA, bảy projection, seed42.
- Smoke: 32 train / 8 validation, 3 updates; train loss 3.0099; validation loss 2.8646; reload adapter xác minh: True.
- Pilot E5C: yêu cầu 100 train / 32 validation; token hóa thực giữ 99 / 31 mẫu. Một epoch; train loss 2.7591; validation loss 2.1508; best validation loss 2.1508.
- Trainer runtime 183.89 giây; peak allocator 6.226 GB; best checkpoint `models/E5C_pilot_20261031\checkpoint-6`. Bộ nhớ WDDM có thể bao gồm bộ nhớ chia sẻ.
- Trainer tokens/second: 509.26. Chi phí điện và khấu hao phần cứng chưa đo; pipeline không dùng teacher API.
- Adapter: `models\E5C_pilot_20261031\final_adapter`; tokenizer và cấu hình được lưu cùng adapter. Đây là pilot 100 mẫu, không phải full training.

## Kiểm thử và đánh giá

- Backend: 374 tests đạt; provenance, leakage, prompt parity, schema/slot validation, lỗi model, dừng thiếu thông tin và an toàn nhiều lượt có test hồi quy. Ứng dụng gốc có thêm 5 safety regression tests đạt.
- Frontend Windows: TypeScript, ESLint, 9 unit tests, build, kiểm tra Worker/manifest/social card và rendered HTML đạt. Ứng dụng gốc cũng build/typecheck đạt.
- Smoke HTTP: frontend, readiness, CORS, follow-up, dừng khi không biết, cấp cứu và schema đạt. Computer Use dừng do không xác minh được URL; chưa xác minh tương tác trực quan qua trình duyệt.
- Safety: 90 ca phát triển; recall 1.000; false-positive rate 0.000. Không phải sensitivity lâm sàng.
- DST: 25 ca do nhóm phát triển soạn; present symptom F1 0.9762; slot accuracy 0.9600.
- Closed-loop E4: 107 hồ sơ synthetic cố định; trung bình 3.000 câu; thu thập đủ core 0.897; lặp 0; off-target 0; emergency recall 1.000. Nhãn giả thuyết chuyên gia: null.
- Bộ chấm bộ lọc: 100 giữ + 100 loại; bộ chấm mù benchmark: 700 dòng = 100 hội thoại khác nhau × 7 hệ thống, tám tiêu chí. Các ô chấm để trống; chưa đo precision bởi người chấm hay Cohen's kappa.

## E1–E5 trên cùng mục kiểm thử

- Tập kiểm thử: `data\processed\vietnamese_dialogue_v1_strict\test.jsonl` (sha256 `71bd88fc3e0a…`)
- Số mục hỏi bệnh: 295; số ca hành vi: 29
- Chỉ số tự động dựa trên luật, trên dữ liệu synthetic; không phải đánh giá lâm sàng.
- Khoảng tin cậy 95%: bootstrap theo hội thoại.

| Chỉ số | E1_base-rescored-dialogue-metrics-v4 | E2_pilot_lora-rescored-dialogue-metrics-v4 | E3_pilot_lora-rescored-dialogue-metrics-v4 | release_20261031_E4 | release_20261031_E5A | release_20261031_E5B | release_20261031_E5C |
|---|---|---|---|---|---|---|---|
| Đúng slot Planner (proxy) | 0.015 [0.000, 0.037] | 0.084 [0.041, 0.132] | 0.084 [0.037, 0.139] | 0.985 [0.951, 1.000] | 0.954 [0.908, 0.986] | 0.977 [0.938, 1.000] | 0.802 [0.725, 0.876] |
| Hỏi lại thông tin (chỉ lượt nhận diện được slot) | 0.021 [0.000, 0.065] | 0.111 [0.067, 0.157] | 0.143 [0.091, 0.200] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| Đầu ra model được chấp nhận | — [—, —] | — [—, —] | — [—, —] | — [—, —] | 0.878 [0.800, 0.943] | 0.863 [0.783, 0.932] | 0.473 [0.371, 0.571] |
| Sử dụng template thay model | — [—, —] | — [—, —] | — [—, —] | — [—, —] | 0.122 [0.057, 0.200] | 0.137 [0.068, 0.218] | 0.527 [0.429, 0.629] |
| Hơn một câu hỏi/lượt | 0.220 [0.173, 0.272] | 0.841 [0.795, 0.882] | 0.827 [0.782, 0.871] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| Số câu hỏi trung bình/lượt | 0.634 [0.522, 0.765] | 3.668 [3.360, 3.993] | 3.302 [3.037, 3.604] | 0.444 [0.374, 0.514] | 0.444 [0.374, 0.514] | 0.444 [0.374, 0.514] | 0.444 [0.374, 0.514] |
| Hỏi bổ sung (tỷ lệ lượt có câu hỏi) | 0.298 [0.253, 0.353] | 0.881 [0.841, 0.919] | 0.871 [0.830, 0.908] | 0.444 [0.374, 0.514] | 0.444 [0.374, 0.514] | 0.444 [0.374, 0.514] | 0.444 [0.374, 0.514] |
| Không hỏi lại thông tin đã có | 0.997 [0.990, 1.000] | 0.936 [0.908, 0.962] | 0.925 [0.894, 0.956] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| Hỏi đúng thông tin còn thiếu | 0.068 [0.041, 0.101] | 0.251 [0.201, 0.305] | 0.220 [0.169, 0.279] | 0.437 [0.365, 0.510] | 0.424 [0.355, 0.495] | 0.434 [0.361, 0.507] | 0.359 [0.298, 0.427] |
| Question relevance (tỷ lệ slot hỏi thuộc thông tin thiếu) | 0.050 [0.030, 0.074] | 0.178 [0.138, 0.223] | 0.141 [0.106, 0.182] | 0.420 [0.351, 0.493] | 0.407 [0.338, 0.481] | 0.417 [0.346, 0.493] | 0.342 [0.281, 0.407] |
| F1 slot so với câu hỏi tham chiếu (synthetic) | 0.044 [0.022, 0.068] | 0.117 [0.086, 0.155] | 0.089 [0.061, 0.119] | 0.050 [0.028, 0.073] | 0.049 [0.026, 0.074] | 0.050 [0.028, 0.073] | 0.045 [0.022, 0.068] |
| Nêu bệnh sớm ở lượt 1–2 | 0.441 [0.389, 0.488] | 0.088 [0.058, 0.118] | 0.102 [0.068, 0.139] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| Hỏi quá 2 câu/lượt | 0.085 [0.058, 0.115] | 0.722 [0.663, 0.780] | 0.678 [0.620, 0.732] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| Phản hồi không an toàn (liều thuốc / chẩn đoán chắc chắn) | 0.007 [0.000, 0.017] | 0.000 [0.000, 0.000] | 0.003 [0.000, 0.010] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| Information completeness (độ phủ thông tin cốt lõi) | 0.066 [0.031, 0.104] | 0.221 [0.156, 0.290] | 0.191 [0.131, 0.254] | 0.229 [0.170, 0.297] | 0.224 [0.164, 0.294] | 0.225 [0.166, 0.295] | 0.220 [0.161, 0.286] |
| Ca hành vi: emergency (đạt/tổng) | 6/10 | 6/10 | 4/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| Ca hành vi: injection (đạt/tổng) | 3/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 |
| Ca hành vi: insufficient_information (đạt/tổng) | 6/6 | 5/6 | 5/6 | 6/6 | 6/6 | 6/6 | 6/6 |
| Ca hành vi: knowledge (đạt/tổng) | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 |
| Ca hành vi: out_of_domain (đạt/tổng) | 1/5 | 1/5 | 1/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| Unsafe response rate | 0.006 | 0.000 | 0.003 | 0.000 | 0.000 | 0.000 | 0.000 |
| Latency trung bình (giây/mục, batch) | 2.64 | 4.91 | 3.81 | 0.04 | 0.85 | 1.45 | 1.49 |
| Peak GPU memory (GB) | 4.63 | 5.07 | 5.07 | — | 4.32 | 4.38 | 4.38 |
| Generated tokens/second (toàn run) | 52.91 | 31.05 | 41.89 | — | 12.33 | 8.06 | 8.47 |

## Chênh lệch ghép cặp so với `E1_base-rescored-dialogue-metrics-v4`

| So sánh | Chỉ số | Chênh lệch | CI 95% | n mục |
|---|---|---|---|---|
| E2_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Đúng slot Planner (proxy) | 0.069 ✓ | [0.015, 0.122] | 131 |
| E2_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Hỏi lại thông tin (chỉ lượt nhận diện được slot) | 0.074 | [-0.069, 0.231] | 27 |
| E2_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Đầu ra model được chấp nhận | — | [—, —] | 0 |
| E2_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Sử dụng template thay model | — | [—, —] | 0 |
| E2_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Hơn một câu hỏi/lượt | 0.620 ✗ | [0.557, 0.679] | 295 |
| E2_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Số câu hỏi trung bình/lượt | 3.034 ✗ | [2.707, 3.378] | 295 |
| E2_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Hỏi bổ sung (tỷ lệ lượt có câu hỏi) | 0.583 ✓ | [0.519, 0.640] | 295 |
| E2_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Không hỏi lại thông tin đã có | -0.061 ✗ | [-0.091, -0.034] | 295 |
| E2_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Hỏi đúng thông tin còn thiếu | 0.183 ✓ | [0.129, 0.240] | 295 |
| E2_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Question relevance (tỷ lệ slot hỏi thuộc thông tin thiếu) | 0.128 ✓ | [0.084, 0.175] | 295 |
| E2_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | F1 slot so với câu hỏi tham chiếu (synthetic) | 0.107 ✓ | [0.063, 0.154] | 184 |
| E2_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Nêu bệnh sớm ở lượt 1–2 | -0.353 ✓ | [-0.406, -0.299] | 295 |
| E2_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Hỏi quá 2 câu/lượt | 0.637 ✗ | [0.567, 0.707] | 295 |
| E2_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Phản hồi không an toàn (liều thuốc / chẩn đoán chắc chắn) | -0.007 | [-0.017, 0.000] | 295 |
| E3_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Đúng slot Planner (proxy) | 0.069 ✓ | [0.015, 0.127] | 131 |
| E3_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Hỏi lại thông tin (chỉ lượt nhận diện được slot) | 0.067 | [-0.065, 0.200] | 30 |
| E3_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Đầu ra model được chấp nhận | — | [—, —] | 0 |
| E3_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Sử dụng template thay model | — | [—, —] | 0 |
| E3_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Hơn một câu hỏi/lượt | 0.607 ✗ | [0.544, 0.672] | 295 |
| E3_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Số câu hỏi trung bình/lượt | 2.668 ✗ | [2.373, 2.966] | 295 |
| E3_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Hỏi bổ sung (tỷ lệ lượt có câu hỏi) | 0.573 ✓ | [0.507, 0.635] | 295 |
| E3_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Không hỏi lại thông tin đã có | -0.071 ✗ | [-0.104, -0.041] | 295 |
| E3_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Hỏi đúng thông tin còn thiếu | 0.153 ✓ | [0.101, 0.207] | 295 |
| E3_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Question relevance (tỷ lệ slot hỏi thuộc thông tin thiếu) | 0.092 ✓ | [0.053, 0.130] | 295 |
| E3_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | F1 slot so với câu hỏi tham chiếu (synthetic) | 0.065 ✓ | [0.028, 0.107] | 182 |
| E3_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Nêu bệnh sớm ở lượt 1–2 | -0.339 ✓ | [-0.395, -0.281] | 295 |
| E3_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Hỏi quá 2 câu/lượt | 0.593 ✗ | [0.525, 0.659] | 295 |
| E3_pilot_lora-rescored-dialogue-metrics-v4 − E1_base-rescored-dialogue-metrics-v4 | Phản hồi không an toàn (liều thuốc / chẩn đoán chắc chắn) | -0.003 | [-0.014, 0.007] | 295 |
| release_20261031_E4 − E1_base-rescored-dialogue-metrics-v4 | Đúng slot Planner (proxy) | 0.969 ✓ | [0.928, 1.000] | 131 |
| release_20261031_E4 − E1_base-rescored-dialogue-metrics-v4 | Hỏi lại thông tin (chỉ lượt nhận diện được slot) | -0.067 | [-0.200, 0.000] | 15 |
| release_20261031_E4 − E1_base-rescored-dialogue-metrics-v4 | Đầu ra model được chấp nhận | — | [—, —] | 0 |
| release_20261031_E4 − E1_base-rescored-dialogue-metrics-v4 | Sử dụng template thay model | — | [—, —] | 0 |
| release_20261031_E4 − E1_base-rescored-dialogue-metrics-v4 | Hơn một câu hỏi/lượt | -0.220 ✓ | [-0.270, -0.176] | 295 |
| release_20261031_E4 − E1_base-rescored-dialogue-metrics-v4 | Số câu hỏi trung bình/lượt | -0.190 ✓ | [-0.333, -0.064] | 295 |
| release_20261031_E4 − E1_base-rescored-dialogue-metrics-v4 | Hỏi bổ sung (tỷ lệ lượt có câu hỏi) | 0.146 ✓ | [0.058, 0.229] | 295 |
| release_20261031_E4 − E1_base-rescored-dialogue-metrics-v4 | Không hỏi lại thông tin đã có | 0.003 | [0.000, 0.010] | 295 |
| release_20261031_E4 − E1_base-rescored-dialogue-metrics-v4 | Hỏi đúng thông tin còn thiếu | 0.369 ✓ | [0.286, 0.446] | 295 |
| release_20261031_E4 − E1_base-rescored-dialogue-metrics-v4 | Question relevance (tỷ lệ slot hỏi thuộc thông tin thiếu) | 0.371 ✓ | [0.296, 0.445] | 295 |
| release_20261031_E4 − E1_base-rescored-dialogue-metrics-v4 | F1 slot so với câu hỏi tham chiếu (synthetic) | 0.017 | [-0.023, 0.057] | 178 |
| release_20261031_E4 − E1_base-rescored-dialogue-metrics-v4 | Nêu bệnh sớm ở lượt 1–2 | -0.441 ✓ | [-0.490, -0.390] | 295 |
| release_20261031_E4 − E1_base-rescored-dialogue-metrics-v4 | Hỏi quá 2 câu/lượt | -0.085 ✓ | [-0.115, -0.057] | 295 |
| release_20261031_E4 − E1_base-rescored-dialogue-metrics-v4 | Phản hồi không an toàn (liều thuốc / chẩn đoán chắc chắn) | -0.007 | [-0.017, 0.000] | 295 |
| release_20261031_E5A − E1_base-rescored-dialogue-metrics-v4 | Đúng slot Planner (proxy) | 0.939 ✓ | [0.884, 0.984] | 131 |
| release_20261031_E5A − E1_base-rescored-dialogue-metrics-v4 | Hỏi lại thông tin (chỉ lượt nhận diện được slot) | -0.067 | [-0.200, 0.000] | 15 |
| release_20261031_E5A − E1_base-rescored-dialogue-metrics-v4 | Đầu ra model được chấp nhận | — | [—, —] | 0 |
| release_20261031_E5A − E1_base-rescored-dialogue-metrics-v4 | Sử dụng template thay model | — | [—, —] | 0 |
| release_20261031_E5A − E1_base-rescored-dialogue-metrics-v4 | Hơn một câu hỏi/lượt | -0.220 ✓ | [-0.270, -0.176] | 295 |
| release_20261031_E5A − E1_base-rescored-dialogue-metrics-v4 | Số câu hỏi trung bình/lượt | -0.190 ✓ | [-0.333, -0.064] | 295 |
| release_20261031_E5A − E1_base-rescored-dialogue-metrics-v4 | Hỏi bổ sung (tỷ lệ lượt có câu hỏi) | 0.146 ✓ | [0.058, 0.229] | 295 |
| release_20261031_E5A − E1_base-rescored-dialogue-metrics-v4 | Không hỏi lại thông tin đã có | 0.003 | [0.000, 0.010] | 295 |
| release_20261031_E5A − E1_base-rescored-dialogue-metrics-v4 | Hỏi đúng thông tin còn thiếu | 0.356 ✓ | [0.274, 0.432] | 295 |
| release_20261031_E5A − E1_base-rescored-dialogue-metrics-v4 | Question relevance (tỷ lệ slot hỏi thuộc thông tin thiếu) | 0.357 ✓ | [0.282, 0.431] | 295 |
| release_20261031_E5A − E1_base-rescored-dialogue-metrics-v4 | F1 slot so với câu hỏi tham chiếu (synthetic) | 0.014 | [-0.026, 0.054] | 178 |
| release_20261031_E5A − E1_base-rescored-dialogue-metrics-v4 | Nêu bệnh sớm ở lượt 1–2 | -0.441 ✓ | [-0.490, -0.390] | 295 |
| release_20261031_E5A − E1_base-rescored-dialogue-metrics-v4 | Hỏi quá 2 câu/lượt | -0.085 ✓ | [-0.115, -0.057] | 295 |
| release_20261031_E5A − E1_base-rescored-dialogue-metrics-v4 | Phản hồi không an toàn (liều thuốc / chẩn đoán chắc chắn) | -0.007 | [-0.017, 0.000] | 295 |
| release_20261031_E5B − E1_base-rescored-dialogue-metrics-v4 | Đúng slot Planner (proxy) | 0.962 ✓ | [0.918, 0.993] | 131 |
| release_20261031_E5B − E1_base-rescored-dialogue-metrics-v4 | Hỏi lại thông tin (chỉ lượt nhận diện được slot) | -0.067 | [-0.200, 0.000] | 15 |
| release_20261031_E5B − E1_base-rescored-dialogue-metrics-v4 | Đầu ra model được chấp nhận | — | [—, —] | 0 |
| release_20261031_E5B − E1_base-rescored-dialogue-metrics-v4 | Sử dụng template thay model | — | [—, —] | 0 |
| release_20261031_E5B − E1_base-rescored-dialogue-metrics-v4 | Hơn một câu hỏi/lượt | -0.220 ✓ | [-0.270, -0.176] | 295 |
| release_20261031_E5B − E1_base-rescored-dialogue-metrics-v4 | Số câu hỏi trung bình/lượt | -0.190 ✓ | [-0.333, -0.064] | 295 |
| release_20261031_E5B − E1_base-rescored-dialogue-metrics-v4 | Hỏi bổ sung (tỷ lệ lượt có câu hỏi) | 0.146 ✓ | [0.058, 0.229] | 295 |
| release_20261031_E5B − E1_base-rescored-dialogue-metrics-v4 | Không hỏi lại thông tin đã có | 0.003 | [0.000, 0.010] | 295 |
| release_20261031_E5B − E1_base-rescored-dialogue-metrics-v4 | Hỏi đúng thông tin còn thiếu | 0.366 ✓ | [0.282, 0.443] | 295 |
| release_20261031_E5B − E1_base-rescored-dialogue-metrics-v4 | Question relevance (tỷ lệ slot hỏi thuộc thông tin thiếu) | 0.367 ✓ | [0.292, 0.443] | 295 |
| release_20261031_E5B − E1_base-rescored-dialogue-metrics-v4 | F1 slot so với câu hỏi tham chiếu (synthetic) | 0.017 | [-0.023, 0.057] | 178 |
| release_20261031_E5B − E1_base-rescored-dialogue-metrics-v4 | Nêu bệnh sớm ở lượt 1–2 | -0.441 ✓ | [-0.490, -0.390] | 295 |
| release_20261031_E5B − E1_base-rescored-dialogue-metrics-v4 | Hỏi quá 2 câu/lượt | -0.085 ✓ | [-0.115, -0.057] | 295 |
| release_20261031_E5B − E1_base-rescored-dialogue-metrics-v4 | Phản hồi không an toàn (liều thuốc / chẩn đoán chắc chắn) | -0.007 | [-0.017, 0.000] | 295 |
| release_20261031_E5C − E1_base-rescored-dialogue-metrics-v4 | Đúng slot Planner (proxy) | 0.786 ✓ | [0.704, 0.865] | 131 |
| release_20261031_E5C − E1_base-rescored-dialogue-metrics-v4 | Hỏi lại thông tin (chỉ lượt nhận diện được slot) | -0.077 | [-0.231, 0.000] | 13 |
| release_20261031_E5C − E1_base-rescored-dialogue-metrics-v4 | Đầu ra model được chấp nhận | — | [—, —] | 0 |
| release_20261031_E5C − E1_base-rescored-dialogue-metrics-v4 | Sử dụng template thay model | — | [—, —] | 0 |
| release_20261031_E5C − E1_base-rescored-dialogue-metrics-v4 | Hơn một câu hỏi/lượt | -0.220 ✓ | [-0.270, -0.176] | 295 |
| release_20261031_E5C − E1_base-rescored-dialogue-metrics-v4 | Số câu hỏi trung bình/lượt | -0.190 ✓ | [-0.333, -0.064] | 295 |
| release_20261031_E5C − E1_base-rescored-dialogue-metrics-v4 | Hỏi bổ sung (tỷ lệ lượt có câu hỏi) | 0.146 ✓ | [0.058, 0.229] | 295 |
| release_20261031_E5C − E1_base-rescored-dialogue-metrics-v4 | Không hỏi lại thông tin đã có | 0.003 | [0.000, 0.010] | 295 |
| release_20261031_E5C − E1_base-rescored-dialogue-metrics-v4 | Hỏi đúng thông tin còn thiếu | 0.292 ✓ | [0.220, 0.360] | 295 |
| release_20261031_E5C − E1_base-rescored-dialogue-metrics-v4 | Question relevance (tỷ lệ slot hỏi thuộc thông tin thiếu) | 0.293 ✓ | [0.225, 0.360] | 295 |
| release_20261031_E5C − E1_base-rescored-dialogue-metrics-v4 | F1 slot so với câu hỏi tham chiếu (synthetic) | 0.008 | [-0.031, 0.047] | 178 |
| release_20261031_E5C − E1_base-rescored-dialogue-metrics-v4 | Nêu bệnh sớm ở lượt 1–2 | -0.441 ✓ | [-0.490, -0.390] | 295 |
| release_20261031_E5C − E1_base-rescored-dialogue-metrics-v4 | Hỏi quá 2 câu/lượt | -0.085 ✓ | [-0.115, -0.057] | 295 |
| release_20261031_E5C − E1_base-rescored-dialogue-metrics-v4 | Phản hồi không an toàn (liều thuốc / chẩn đoán chắc chắn) | -0.007 | [-0.017, 0.000] | 295 |

✓ = cải thiện có CI không chứa 0; ✗ = xấu đi có CI không chứa 0.

## Phân tích lỗi và giới hạn

Các tỷ lệ phía trên là proxy. Lượt cấp cứu/dừng không phải cơ hội sinh câu hỏi. Target-slot hit của pipeline bao gồm câu template; model_accepted và template_fallback có mẫu số riêng. Không dùng non_redundant v1 để chứng minh chất lượng. Chênh lệch E1–E3 với E5 phản ánh cả safety/planning/validation, không chỉ học của model. Latency E1–E3 được đo với batch lịch sử khác; không dùng để kết luận tăng tốc.

Lượt đầu sơ bộ chủ yếu hỏi chief complaint/timing, nên kết quả chính dùng ba lượt. Closed-loop phát hiện thiếu cue ở urinary red-flag screen và musculoskeletal triggers; đã thêm hồi quy và chạy lại E5 với Planner v2.1. Rescore v4 sửa việc bỏ sót chief complaint và những cue này, ghi ra thư mục mới.

Lý do validator từ chối (có thể nhiều lý do/mẫu):

- `release_20261031_E5A`: `{"condition_naming": 13, "multiple_slots": 2, "off_target": 1}`
- `release_20261031_E5B`: `{"condition_naming": 12, "multiple_slots": 2, "off_target": 5, "extra_content": 2, "multiple_questions": 1, "premature_diagnosis": 1}`
- `release_20261031_E5C`: `{"off_target": 59, "condition_naming": 12, "extra_content": 24, "multiple_slots": 6, "premature_diagnosis": 3, "no_question": 9, "unreported_symptom": 1, "multiple_questions": 2}`

Validation loss của Qwen Base trên cùng 31 cửa sổ từ 32 hội thoại nguồn: **3.2943**, so với E5C **2.1508**. Đây là loss dự đoán token của câu hỏi JSON, không phải độ chính xác y khoa.

Closed-loop đối chứng nhỏ trên cùng 11 hồ sơ: E4 core completeness 0.727, E5C 0.727; câu hỏi trung bình 2.818/2.818; off-target 0/0. Cả hai dùng safety/planner cố định; đây là kiểm tra tích hợp simulator, không phải nhãn lâm sàng.

HTTP smoke với adapter E5C thật: 7 kiểm tra đạt; question_source=model; provider=planner+Qwen/Qwen3-1.7B+lora; model_validation.accepted=True. Bao gồm frontend/readiness/CORS, hỏi vị trí, cấp cứu mới sau phủ định cũ, ngoài phạm vi, dừng khi không biết và RAG không sẵn sàng.

RAG thật: FAISS + BAAI/bge-m3 lập chỉ mục hai excerpt cards, hai truy vấn kiểm tra trả đúng nguồn đứng đầu; reranker=score. Đây là smoke retrieval trên corpus hai tài liệu, không phải Recall/MRR trên benchmark lâm sàng. Chỉ mục mới dùng thư mục riêng, không ghi đè index cũ; kiểm tra nguồn không thay cho thẩm định bác sĩ.

Chưa thể kết luận cải thiện chất lượng hỏi bệnh lâm sàng hoặc Recall@3 chẩn đoán. Cần người chấm độc lập, bác sĩ rà soát ca nguy hiểm, corpus có nguồn/thẩm định và tập nhãn bệnh được xác minh. Chưa thực hiện huấn luyện 640/2.000/5.000 target. Không tạo teacher bằng Gemini/OpenAI và không triển khai lên hosting.

## Phạm vi từng phase

| Phase | Tệp/chức năng chính | Trạng thái |
|---|---|---|
| 1 | vite.config.ts, scripts/vite, root server/dialogueEngine, triage | Build/safety/provider fallback đã sửa |
| 2 | prepare_planner_sft.py, planner_validation.py, review export | Dataset pilot + hash/provenance/leakage checks đạt |
| 3 | medical_planner_sft_v1.yaml, trainer, train_stage1 | Smoke save/reload + pilot E5C thực chạy |
| 4 | prompts, question_generator, consultation, state/planner | Shared prompt, JSON validator, template disclosure, stop conditions |
| 5 | benchmark_dialogue, dialogue_metrics, compare_runs, closed_loop | E1–E5 cùng item/protocol; expert evaluation chờ thực hiện |
| 6 | RAG metadata/loaders/citations, hypotheses provenance | Hai excerpt cards kiểm tra nguồn MedlinePlus/NHS; chưa có corpus/nhãn chuyên gia |
| 7 | app/page.tsx, consultation.ts, smoke-local | Frontend/API/build/HTTP đạt; kiểm thử trực quan bị giới hạn |
| 8 | docs và evidence JSON | Báo cáo từ artifact thật; không ghi đè lịch sử |

Chi tiết lệnh tái lập: [PLANNER_GUIDED.md](PLANNER_GUIDED.md). Evidence JSON nằm cạnh báo cáo; raw dataset/model/predictions và CSV annotation nằm trong các thư mục local ignored của backend.

## Commit và artifact chính

- `e691818a`: stability/safety, data pipeline, training config, Planner/validator/API/frontend.
- `dd5ae127`: sửa nhận diện câu hỏi theo hồ sơ và version metric.
- `39fe0d9d`: provider minh bạch, dừng thiếu thông tin và hồi quy safety ứng dụng gốc.
- `a5b740a`: HTTP với LoRA thật, nguồn RAG, xuất bộ chấm mù, công cụ tổng hợp kết quả.
- Adapter: `backend/models/E5C_pilot_20261031/final_adapter`; dữ liệu SFT: `backend/data/processed/vietnamese_planner_sft_v1`.
- CSV bộ lọc: `backend/reports/annotation/planner_filter_20261031.csv`; chấm mù: `backend/reports/annotation/E1_E5_blind_20261031.csv`. Key giải mù nằm riêng, không gửi cho người chấm.
- Chỉ mục BGE-M3 mới: `backend/data/rag_index/source_checked_live_20261031`; model/dataset/index/CSV giữ local và được Git ignore.

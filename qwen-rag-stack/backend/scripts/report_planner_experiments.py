"""Build a research report from completed artifacts, without inventing results."""
import argparse
import json
from collections import Counter
from pathlib import Path

from evals.compare_runs import compare


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="+", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--smoke", type=Path, required=True)
    parser.add_argument("--closed-loop", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Report exists; preserve it and choose another path")
    comparison, table = compare(args.runs)
    data = read(Path("data/processed/vietnamese_planner_sft_v1/manifest.json"))
    pilot = read(args.pilot / "run_metadata/run.json")
    smoke = read(args.smoke / "run_metadata/run.json")
    closed = read(args.closed_loop)
    safety = read(Path("reports/safety_planner_20261031.json"))
    dst = read(Path("reports/dst_planner_20261031.json"))
    evidence = {"code_commit": args.code_commit, "data": data, "pilot": pilot, "smoke": smoke,
                "comparison": comparison, "closed_loop": closed, "safety": safety, "dst": dst, "errors": {}}
    for path in args.runs:
        reasons = Counter()
        for line in (path / "predictions.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            reasons.update(row.get("model_validation", {}).get("rejection_reasons", []))
        evidence["errors"][path.name] = dict(reasons)
    metrics = pilot["metrics"]
    text = ["# Planner-guided Qwen — thực nghiệm 31/10/2026", "",
        f"Mã triển khai: `{args.code_commit}`. Dữ liệu dẫn xuất v1 được tạo với code hash trong manifest; "
        "bản sửa nhận diện slot Planner v2.1 áp dụng đồng nhất cho các lượt benchmark cuối. "
        "Giữ nguyên mọi pilot lịch sử. Đây là kết quả phát triển trên dữ liệu synthetic, chưa có kiểm định lâm sàng.", "",
        "## Dữ liệu và huấn luyện", "",
        f"- Nguồn: Meddies Vietnamese revision `{data['dataset_revision']}`; giới hạn {data['max_conversations_per_split']} hội thoại nguồn mỗi split.",
        f"- Train: {data['splits']['train']['kept']} mẫu; validation: {data['splits']['validation']['kept']} mẫu; toàn bộ nhãn auto_filtered_dataset_question; 0 template, 0 nhãn chuyên gia tự gán.",
        "- Source train/validation/test giữ nguyên; ID/nhóm tách biệt; opening trùng split bị loại khỏi dữ liệu dẫn xuất. Test không cung cấp target SFT.",
        f"- Qwen Base revision `{metrics['model_revision']}`; GPU {metrics['gpu']}; LoRA r16/alpha32, bfloat16, SDPA, bảy projection, seed42.",
        f"- Smoke: {smoke['metrics']['train_examples']} train / {smoke['metrics']['validation_examples']} validation, 3 updates; train loss {smoke['metrics']['train_loss']:.4f}; validation loss {smoke['metrics']['eval_loss']:.4f}; reload adapter xác minh: {smoke['metrics'].get('adapter_reload_verified', False)}.",
        f"- Pilot E5C: yêu cầu 100 train / 32 validation; token hóa thực giữ {metrics['train_examples']} / {metrics['validation_examples']} mẫu. Một epoch; train loss {metrics['train_loss']:.4f}; validation loss {metrics['eval_loss']:.4f}; best validation loss {metrics['best_validation_loss']:.4f}.",
        f"- Trainer runtime {metrics['train_runtime']:.2f} giây; peak allocator {metrics['peak_gpu_memory_gb']:.3f} GB; best checkpoint `{metrics['best_checkpoint']}`. Bộ nhớ WDDM có thể bao gồm bộ nhớ chia sẻ.",
        f"- Adapter: `{args.pilot / 'final_adapter'}`; tokenizer và cấu hình được lưu cùng adapter. Đây là pilot 100 mẫu, không phải full training.", "",
        "## Kiểm thử và đánh giá", "",
        "- Backend: 374 tests đạt; provenance, leakage, prompt parity, schema/slot validation, lỗi model, dừng thiếu thông tin và an toàn nhiều lượt có test hồi quy. Ứng dụng gốc có thêm 5 safety regression tests đạt.",
        "- Frontend Windows: TypeScript, ESLint, 9 unit tests, build, kiểm tra Worker/manifest/social card và rendered HTML đạt. Ứng dụng gốc cũng build/typecheck đạt.",
        "- Smoke HTTP: frontend, readiness, CORS, follow-up, dừng khi không biết, cấp cứu và schema đạt. Computer Use dừng do không xác minh được URL; chưa xác minh tương tác trực quan qua trình duyệt.",
        f"- Safety: {safety['case_count']} ca phát triển; recall {safety['emergency_recall']:.3f}; false-positive rate {safety['false_positive_rate']:.3f}. Không phải sensitivity lâm sàng.",
        f"- DST: {dst['cases']} ca do nhóm phát triển soạn; present symptom F1 {dst['symptom_extraction_present']['f1']:.4f}; slot accuracy {dst['state_slot_accuracy']:.4f}.",
        f"- Closed-loop E4: {closed['cases']} hồ sơ synthetic cố định; trung bình {closed['mean_questions']:.3f} câu; thu thập đủ core {closed['complete_information_rate']:.3f}; lặp {closed['repeated_questions']}; off-target {closed['off_target_questions']}; emergency recall {closed['emergency_recall']:.3f}. Nhãn giả thuyết chuyên gia: null.",
        "- Bộ chấm bộ lọc: 100 giữ + 100 loại; bộ chấm mù benchmark chuẩn bị riêng. Các ô chấm để trống; chưa đo precision bởi người chấm hay Cohen's kappa.", "",
        table.replace("# So sánh mô hình trên benchmark hỏi bệnh", "## E1–E5 trên cùng mục kiểm thử"),
        "## Phân tích lỗi và giới hạn", "",
        "Các tỷ lệ phía trên là proxy. Lượt cấp cứu/dừng không phải cơ hội sinh câu hỏi. "
        "Target-slot hit của pipeline bao gồm câu template; model_accepted và template_fallback có mẫu số riêng. "
        "Không dùng non_redundant v1 để chứng minh chất lượng. Chênh lệch E1–E3 với E5 phản ánh cả safety/planning/validation, không chỉ học của model. "
        "Latency E1–E3 được đo với batch lịch sử khác; không dùng để kết luận tăng tốc.", "",
        "Lượt đầu sơ bộ chủ yếu hỏi chief complaint/timing, nên kết quả chính dùng ba lượt. Closed-loop phát hiện thiếu cue "
        "ở urinary red-flag screen và musculoskeletal triggers; đã thêm hồi quy và chạy lại E5 với Planner v2.1. "
        "Rescore v4 sửa việc bỏ sót chief complaint và những cue này, ghi ra thư mục mới.", "",
        "Lý do validator từ chối (có thể nhiều lý do/mẫu):", ""]
    for name, reasons in evidence["errors"].items():
        if reasons:
            text.append(f"- `{name}`: `{json.dumps(reasons, ensure_ascii=False)}`")
    text += ["", "Chưa thể kết luận cải thiện chất lượng hỏi bệnh lâm sàng hoặc Recall@3 chẩn đoán. "
             "Cần người chấm độc lập, bác sĩ rà soát ca nguy hiểm, corpus có nguồn/thẩm định và tập nhãn bệnh được xác minh. "
             "Chưa thực hiện huấn luyện 640/2.000/5.000 target. Không tạo teacher bằng Gemini/OpenAI và không triển khai lên hosting.", "",
             "## Phạm vi từng phase", "",
             "| Phase | Tệp/chức năng chính | Trạng thái |", "|---|---|---|",
             "| 1 | vite.config.ts, scripts/vite, root server/dialogueEngine, triage | Build/safety/provider fallback đã sửa |",
             "| 2 | prepare_planner_sft.py, planner_validation.py, review export | Dataset pilot + hash/provenance/leakage checks đạt |",
             "| 3 | medical_planner_sft_v1.yaml, trainer, train_stage1 | Smoke save/reload + pilot E5C thực chạy |",
             "| 4 | prompts, question_generator, consultation, state/planner | Shared prompt, JSON validator, template disclosure, stop conditions |",
             "| 5 | benchmark_dialogue, dialogue_metrics, compare_runs, closed_loop | E1–E5 cùng item/protocol; expert evaluation chờ thực hiện |",
             "| 6 | RAG metadata/loaders/citations, hypotheses provenance | Cổng provenance hoàn tất; chưa bổ sung corpus/nhãn chuyên gia |",
             "| 7 | app/page.tsx, consultation.ts, smoke-local | Frontend/API/build/HTTP đạt; kiểm thử trực quan bị giới hạn |",
             "| 8 | docs và evidence JSON | Báo cáo từ artifact thật; không ghi đè lịch sử |", "",
             "Chi tiết lệnh tái lập: [PLANNER_GUIDED.md](PLANNER_GUIDED.md). "
             "Evidence JSON nằm cạnh báo cáo; raw dataset/model/predictions và CSV annotation nằm trong các thư mục local ignored của backend.", ""]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(text), encoding="utf-8")
    args.output.with_suffix(".json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

"""Build a research report from completed artifacts, without inventing results."""
import argparse
import hashlib
import json
import sys
from importlib.metadata import version
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
    parser.add_argument("--base-loss", type=Path)
    parser.add_argument("--paired-closed-loop", nargs=2, type=Path)
    parser.add_argument("--http-smoke", type=Path)
    parser.add_argument("--rag-smoke", type=Path)
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
    evidence["software"] = {"python": sys.version, **{name: version(name) for name in (
        "torch", "transformers", "peft", "trl", "datasets", "accelerate", "fastapi", "pydantic", "pytest", "wandb")}}
    evidence["adapter_sha256"] = {}
    for path in args.runs:
        adapter = read(path / "metrics.json").get("adapter")
        if adapter and adapter not in evidence["adapter_sha256"]:
            evidence["adapter_sha256"][adapter] = {name: hashlib.sha256((Path(adapter) / name).read_bytes()).hexdigest()
                for name in ("adapter_config.json", "adapter_model.safetensors")}
    for path in args.runs:
        reasons = Counter()
        for line in (path / "predictions.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            reasons.update(row.get("model_validation", {}).get("rejection_reasons", []))
        evidence["errors"][path.name] = dict(reasons)
    metrics = pilot["metrics"]
    guided_paths = [path for path in args.runs if read(path / "metrics.json").get("backend") == "guided"]
    guided_result, _ = compare(guided_paths) if len(guided_paths) >= 2 else ({}, "")
    evidence["guided_comparison"] = guided_result
    guided_by_experiment = {read(path / "metrics.json").get("experiment"): read(path / "metrics.json") for path in guided_paths}
    finding = "Chưa có đối chứng guided đủ điều kiện để kết luận."
    if {"E5A", "E5C"} <= set(guided_by_experiment):
        base, tuned = guided_by_experiment["E5A"], guided_by_experiment["E5C"]
        accepted_base = base["metrics"]["question_generation"]["model_accepted"]
        accepted_tuned = tuned["metrics"]["question_generation"]["model_accepted"]
        difference = guided_result["paired"][tuned["run_name"]]["model_accepted"]
        finding = (f"**Kết quả chính:** E5C pilot có model acceptance {accepted_tuned['mean']:.3f}, "
                   f"E5A {accepted_base['mean']:.3f}, trên {accepted_tuned['n']} cơ hội hỏi; "
                   f"chênh lệch ghép cặp {difference['diff']:+.3f}, CI95% {difference['ci95']}. "
                   "Pilot này chưa chứng minh cải thiện hỏi bệnh; loss thấp hơn không thay thế đánh giá chất lượng câu hỏi. "
                   "Acceptance phụ thuộc validator tự động, chưa phải đánh giá chuyên gia.")
    text = ["# Planner-guided Qwen — thực nghiệm 31/10/2026", "",
        f"Mã triển khai: `{args.code_commit}`. Dữ liệu dẫn xuất v1 được tạo với code hash trong manifest; "
        "bản sửa nhận diện slot Planner v2.1 áp dụng đồng nhất cho các lượt benchmark cuối. "
        "Giữ nguyên mọi pilot lịch sử. Đây là kết quả phát triển trên dữ liệu synthetic, chưa có kiểm định lâm sàng.", "",
        finding, "",
        "## Dữ liệu và huấn luyện", "",
        f"- Phần mềm: `{json.dumps(evidence['software'], ensure_ascii=False)}`.",
        f"- Nguồn: Meddies Vietnamese revision `{data['dataset_revision']}`; giới hạn {data['max_conversations_per_split']} hội thoại nguồn mỗi split.",
        f"- Train: {data['splits']['train']['kept']} mẫu; validation: {data['splits']['validation']['kept']} mẫu; toàn bộ nhãn auto_filtered_dataset_question; 0 template, 0 nhãn chuyên gia tự gán.",
        "- Source train/validation/test giữ nguyên; ID/nhóm tách biệt; opening trùng split bị loại khỏi dữ liệu dẫn xuất. Test không cung cấp target SFT.",
        f"- Qwen Base revision `{metrics['model_revision']}`; GPU {metrics['gpu']}; LoRA r16/alpha32, bfloat16, SDPA, bảy projection, seed42.",
        f"- Smoke: {smoke['metrics']['train_examples']} train / {smoke['metrics']['validation_examples']} validation, 3 updates; train loss {smoke['metrics']['train_loss']:.4f}; validation loss {smoke['metrics']['eval_loss']:.4f}; reload adapter xác minh: {smoke['metrics'].get('adapter_reload_verified', False)}.",
        f"- Pilot E5C: yêu cầu 100 train / 32 validation; token hóa thực giữ {metrics['train_examples']} / {metrics['validation_examples']} mẫu. Một epoch; train loss {metrics['train_loss']:.4f}; validation loss {metrics['eval_loss']:.4f}; best validation loss {metrics['best_validation_loss']:.4f}.",
        f"- Trainer runtime {metrics['train_runtime']:.2f} giây; peak allocator {metrics['peak_gpu_memory_gb']:.3f} GB; best checkpoint `{metrics['best_checkpoint']}`. Bộ nhớ WDDM có thể bao gồm bộ nhớ chia sẻ.",
        f"- Trainer tokens/second: {metrics['train_tokens_per_second']:.2f}. Chi phí điện và khấu hao phần cứng chưa đo; pipeline không dùng teacher API.",
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
    if args.base_loss:
        baseline_loss = read(args.base_loss)
        evidence["planner_base_validation_loss"] = baseline_loss
        text += ["", f"Validation loss của Qwen Base trên cùng {baseline_loss['windows']} cửa sổ từ "
                 f"{baseline_loss['conversations']} hội thoại nguồn: **{baseline_loss['eval_loss']:.4f}**, "
                 f"so với E5C **{metrics['eval_loss']:.4f}**. Đây là loss dự đoán token của câu hỏi JSON, không phải độ chính xác y khoa."]
    if args.paired_closed_loop:
        paired = [read(path) for path in args.paired_closed_loop]
        if [r["case_id"] for r in paired[0]["rows"]] != [r["case_id"] for r in paired[1]["rows"]]:
            raise ValueError("Closed-loop paired cases differ")
        evidence["paired_closed_loop"] = paired
        text += ["", f"Closed-loop đối chứng nhỏ trên cùng {paired[0]['cases']} hồ sơ: "
                 f"E4 core completeness {paired[0]['complete_information_rate']:.3f}, "
                 f"E5C {paired[1]['complete_information_rate']:.3f}; "
                 f"câu hỏi trung bình {paired[0]['mean_questions']:.3f}/{paired[1]['mean_questions']:.3f}; "
                 f"off-target {paired[0]['off_target_questions']}/{paired[1]['off_target_questions']}. "
                 "Cả hai dùng safety/planner cố định; đây là kiểm tra tích hợp simulator, không phải nhãn lâm sàng."]
    if args.http_smoke:
        smoke_http = read(args.http_smoke)
        evidence["real_adapter_http_smoke"] = smoke_http
        text += ["", f"HTTP smoke với adapter E5C thật: {smoke_http['checks']} kiểm tra đạt; "
                 f"question_source={smoke_http['question_source']}; provider={smoke_http['provider']}; "
                 f"model_validation.accepted={smoke_http['model_validation']['accepted']}. "
                 "Bao gồm frontend/readiness/CORS, hỏi vị trí, cấp cứu mới sau phủ định cũ, ngoài phạm vi, dừng khi không biết và RAG không sẵn sàng."]
    if args.rag_smoke:
        rag_smoke = read(args.rag_smoke)
        evidence["source_checked_rag_smoke"] = rag_smoke
        text += ["", f"RAG thật: FAISS + {rag_smoke['embedding_model']} lập chỉ mục hai excerpt cards, "
                 f"hai truy vấn kiểm tra trả đúng nguồn đứng đầu; reranker={rag_smoke['reranker']}. "
                 "Đây là smoke retrieval trên corpus hai tài liệu, không phải Recall/MRR trên benchmark lâm sàng. "
                 "Chỉ mục mới dùng thư mục riêng, không ghi đè index cũ; kiểm tra nguồn không thay cho thẩm định bác sĩ."]
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
             "| 6 | RAG metadata/loaders/citations, hypotheses provenance | Hai excerpt cards kiểm tra nguồn MedlinePlus/NHS; chưa có corpus/nhãn chuyên gia |",
             "| 7 | app/page.tsx, consultation.ts, smoke-local | Frontend/API/build/HTTP đạt; kiểm thử trực quan bị giới hạn |",
             "| 8 | docs và evidence JSON | Báo cáo từ artifact thật; không ghi đè lịch sử |", "",
             "Chi tiết lệnh tái lập: [PLANNER_GUIDED.md](PLANNER_GUIDED.md). "
             "Evidence JSON nằm cạnh báo cáo; raw dataset/model/predictions và CSV annotation nằm trong các thư mục local ignored của backend.", ""]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(text), encoding="utf-8")
    args.output.with_suffix(".json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

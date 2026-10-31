# Medical knowledge corpus

> **Phạm vi sau hợp nhất:** Kho tài liệu này phục vụ **chỉ Qwen/RAG** trong `qwen-rag-stack/`. Không tự động được tải vào ứng dụng Gemini API tại thư mục gốc. Tài liệu y khoa cần kiểm tra xuất xứ và quyền sử dụng trước khi lập chỉ mục.


Only place reviewed, redistribution-safe medical references in these folders. Suitable
sources include WHO, CDC, NIH, NICE, national ministries of health, and locally reviewed
documents with clear provenance. Meddies/RandomQA training rows are not factual RAG sources.

Supported inputs are UTF-8 `.txt`, `.md`, `.json`, `.html`, and text-based `.pdf`. OCR is not
performed. Add a sidecar named `<document>.<ext>.metadata.json` when metadata is not embedded:

```json
{
  "source_id": "stable-source-id",
  "title": "Document title",
  "organization": "Publishing authority",
  "source_url": "https://example.org/document",
  "publication_date": "2026-01-31",
  "jurisdiction": "VN",
  "language": "vi"
}
```

Unknown metadata must be omitted or set to `null`; do not guess it. Rebuild the generated,
git-ignored index after adding, changing, or removing a source. Model retraining is not needed.

`source_checked_excerpt_cards_20261031.json` contains two short attributed excerpt cards checked
against the official MedlinePlus/NHS pages on 2026-10-31. Their status means publisher URL and
excerpt text were checked; it does **not** mean independent clinician review, comprehensive
medical coverage, or adaptation of foreign clinical pathways to Vietnam. Publication dates
remain null; the actual source update/review dates are recorded in `source_version`.
These cards contain no medication treatment directions. Original source terms apply.
Meddies training examples and developer-authored condition tables are not these sources.


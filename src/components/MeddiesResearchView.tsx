import React, { useState, useEffect } from 'react';
import {
  Database,
  Cpu,
  ShieldCheck,
  Search,
  Play,
  RefreshCw,
  CheckCircle2,
  BookOpen,
  Building2,
  SlidersHorizontal,
} from 'lucide-react';
import {
  MEDDIES_DATASET_METADATA,
  MEDDIES_BENCHMARK_EXPERIMENTS,
  MEDDIES_CONVERSATION_SAMPLES,
  MeddiesDatasetSample,
} from '../data/meddiesDatasetSamples';
import { InferenceEngineMode } from '../types/health';
import { normalizeVietnamese } from '../data/medicationCatalog';

interface MeddiesResearchViewProps {
  inferenceMode: InferenceEngineMode;
  onChangeInferenceMode: (mode: InferenceEngineMode) => void;
  onRunSampleInChat: (initialPrompt: string, sampleTitle: string) => void;
}

type ResearchSection = 'overview' | 'explorer' | 'benchmarks';

export const MeddiesResearchView: React.FC<MeddiesResearchViewProps> = ({
  inferenceMode,
  onChangeInferenceMode,
  onRunSampleInChat,
}) => {
  const [activeSection, setActiveSection] =
    useState<ResearchSection>('explorer');
  const [selectedGroup, setSelectedGroup] = useState<string>('Tất cả');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedSample, setSelectedSample] = useState<MeddiesDatasetSample>(
    MEDDIES_CONVERSATION_SAMPLES[0]
  );
  const [backendStatus, setBackendStatus] = useState<{
    checking: boolean;
    cloudHybridReady: boolean;
    qwenOnline: boolean;
    qwenModelReady: boolean;
    qwenRagReady: boolean;
    qwenUrl: string;
  }>({
    checking: false,
    cloudHybridReady: true,
    qwenOnline: false,
    qwenModelReady: false,
    qwenRagReady: false,
    qwenUrl: 'http://localhost:8000',
  });

  const checkStatus = async () => {
    setBackendStatus((prev) => ({ ...prev, checking: true }));
    try {
      const res = await fetch('/api/meddies/status');
      if (res.ok) {
        const data = await res.json();
        setBackendStatus({
          checking: false,
          cloudHybridReady: Boolean(data.cloudHybridReady),
          qwenOnline: Boolean(data.qwenLocal?.online),
          qwenModelReady: Boolean(data.qwenLocal?.modelReady),
          qwenRagReady: Boolean(data.qwenLocal?.ragReady),
          qwenUrl: data.qwenLocal?.url || 'http://localhost:8000',
        });
        return;
      }
    } catch {
      // ignore
    }
    setBackendStatus((prev) => ({ ...prev, checking: false }));
  };

  useEffect(() => {
    void checkStatus();
  }, []);

  const clinicalGroups = [
    'Tất cả',
    'Tiêu hóa',
    'Thần kinh',
    'Hô hấp',
    'Truyền nhiễm & Sốt',
    'Tiết niệu',
    'Da liễu & Dị ứng',
  ];

  const filteredSamples = MEDDIES_CONVERSATION_SAMPLES.filter((sample) => {
    const matchGroup =
      selectedGroup === 'Tất cả' || sample.clinicalGroup === selectedGroup;
    const normSearch = normalizeVietnamese(searchQuery);
    const matchSearch =
      !normSearch ||
      normalizeVietnamese(
        `${sample.targetDisease} ${sample.icd10} ${sample.initialUserPrompt} ${sample.extractedSymptoms.join(' ')}`
      ).includes(normSearch);
    return matchGroup && matchSearch;
  });

  return (
    <div className="space-y-6">
      {/* Thesis Specification & Dual Backend Inference Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-4">
          <div className="space-y-1 max-w-3xl">
            <div className="text-xs font-semibold text-teal-700">
              <span>ĐỀ TÀI NGHIÊN CỨU</span>
              <span aria-hidden="true"> · </span>
              <span>ỨNG DỤNG AI CHO BÀI TOÁN Y TẾ</span>
              <span aria-hidden="true"> · </span>
              <span className="font-mono-tabular">
                DATASET: {MEDDIES_DATASET_METADATA.datasetName}
              </span>
            </div>
            <h2 className="text-lg font-bold text-slate-900">
              Hệ Thống Mô Hình Hội Thoại Y Tế Tiếng Việt & Sàng Lọc Triệu Chứng Đa Lượt
            </h2>
            <p className="text-xs text-slate-600 leading-relaxed">
              Tiếp nhận triệu chứng bằng ngôn ngữ tự nhiên, chủ động đặt câu hỏi
              bổ sung để thu thập thông tin bệnh sử, phân tích hội thoại và dự
              đoán các bệnh có khả năng liên quan kèm thông tin y tế tham khảo
              và khuyến nghị cơ sở y tế (hỗ trợ sàng lọc ban đầu, không thay thế
              chẩn đoán của bác sĩ).
            </p>
          </div>

          {/* Segmented Section Switcher */}
          <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-1">
            {[
              {
                id: 'explorer' as ResearchSection,
                label: 'Khám Phá Mẫu Hội Thoại Meddies',
              },
              {
                id: 'overview' as ResearchSection,
                label: 'Thống Kê & Làm Sạch Dataset',
              },
              {
                id: 'benchmarks' as ResearchSection,
                label: 'Thực Nghiệm Fine-Tune QLoRA',
              },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveSection(tab.id)}
                className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors whitespace-nowrap ${
                  activeSection === tab.id
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Dual Inference Engine Control Bar */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="lg:col-span-5 space-y-1">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-900">
              <SlidersHorizontal className="h-4 w-4 text-teal-600 shrink-0" />
              <span>Cơ Chế Backend Phục Vụ Suy Luận Mô Hình (Chế Độ Kép)</span>
            </div>
            <p className="text-xs text-slate-600">
              Chọn chế độ suy luận cho khung hội thoại tư vấn. Hệ thống tự động
              chuyển dự phòng nếu máy chủ GPU Qwen cục bộ chưa bật.
            </p>
          </div>

          <div className="lg:col-span-5 grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            <button
              type="button"
              onClick={() => onChangeInferenceMode('cloud_hybrid')}
              className={`rounded-lg border p-3 text-left transition-colors ${
                inferenceMode === 'cloud_hybrid'
                  ? 'border-teal-600 bg-white text-slate-900'
                  : 'border-slate-200 bg-slate-100/70 text-slate-600 hover:bg-white'
              }`}
            >
              <div className="flex items-center justify-between text-xs font-bold">
                <span>01. Cloud AI + RAG Meddies</span>
                {inferenceMode === 'cloud_hybrid' && (
                  <CheckCircle2 className="h-4 w-4 text-teal-600 shrink-0" />
                )}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Suy luận trực tuyến + 7-Stage DST + Truy xuất mẫu Meddies
              </p>
            </button>

            <button
              type="button"
              onClick={() => onChangeInferenceMode('qwen_local')}
              className={`rounded-lg border p-3 text-left transition-colors ${
                inferenceMode === 'qwen_local'
                  ? 'border-teal-600 bg-white text-slate-900'
                  : 'border-slate-200 bg-slate-100/70 text-slate-600 hover:bg-white'
              }`}
            >
              <div className="flex items-center justify-between text-xs font-bold">
                <span>02. Qwen Fine-Tune (FastAPI)</span>
                {inferenceMode === 'qwen_local' && (
                  <CheckCircle2 className="h-4 w-4 text-teal-600 shrink-0" />
                )}
              </div>
              <p className="text-xs text-slate-500 mt-1 font-mono-tabular">
                {backendStatus.qwenOnline
                  ? `Đang kết nối (${backendStatus.qwenUrl})`
                  : `Port :8000 (Tự động fallback Cloud)`}
              </p>
            </button>
          </div>

          <div className="lg:col-span-2 flex justify-end">
            <button
              type="button"
              onClick={checkStatus}
              disabled={backendStatus.checking}
              className="flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-100 transition-colors whitespace-nowrap"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 text-teal-600 ${
                  backendStatus.checking ? 'animate-spin' : ''
                }`}
              />
              <span>Kiểm tra cổng</span>
            </button>
          </div>
        </div>
      </div>

      {/* SECTION 1: INTERACTIVE MEDDIES/MEDDIES-CONSULTANT CONVERSATION EXPLORER */}
      {activeSection === 'explorer' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Filter & Sample List */}
          <div className="lg:col-span-5 rounded-xl border border-slate-200 bg-white p-5 space-y-4">
            <div className="border-b border-slate-200 pb-3 space-y-1">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-900">
                  Kho Mẫu Hội Thoại Meddies/meddies-consultant
                </h3>
                <span className="font-mono-tabular text-xs text-slate-500">
                  {filteredSamples.length} kịch bản chuẩn
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Chọn một ca hội thoại thực tế từ tập dữ liệu để xem quy trình
                bác sĩ hỏi thêm thông tin và bấm chạy thử trực tiếp trên Chatbot.
              </p>
            </div>

            {/* Search Input */}
            <div className="relative">
              <Search className="h-4 w-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Tìm theo triệu chứng, tên bệnh hoặc mã ICD-10..."
                className="w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 py-2 text-xs text-slate-900 placeholder:text-slate-400 focus:border-teal-600 focus:outline-none"
              />
            </div>

            {/* Clinical Group Filter Bar */}
            <div className="flex flex-wrap gap-1.5">
              {clinicalGroups.map((grp) => (
                <button
                  key={grp}
                  type="button"
                  onClick={() => setSelectedGroup(grp)}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                    selectedGroup === grp
                      ? 'bg-slate-900 text-white'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  {grp}
                </button>
              ))}
            </div>

            {/* Sample Cards */}
            <div className="space-y-2.5 max-h-[540px] overflow-y-auto pr-1">
              {filteredSamples.map((sample) => {
                const isSelected = sample.id === selectedSample.id;
                return (
                  <div
                    key={sample.id}
                    onClick={() => setSelectedSample(sample)}
                    className={`cursor-pointer rounded-lg border p-3.5 transition-colors space-y-2 ${
                      isSelected
                        ? 'border-teal-600 bg-teal-50/40'
                        : 'border-slate-200 bg-white hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 text-xs text-slate-500 font-mono-tabular">
                      <span>
                        {sample.clinicalGroup} · ID: {sample.conversationId}
                      </span>
                      <span>ICD-10: {sample.icd10}</span>
                    </div>
                    <h4 className="text-xs font-bold text-slate-900">
                      {sample.targetDisease}
                    </h4>
                    <p className="text-xs text-slate-600 line-clamp-2">
                      “{sample.initialUserPrompt}”
                    </p>
                    <div className="flex items-center justify-between pt-1 text-xs text-slate-500">
                      <span>
                        Mức lọc: {sample.qualityLevel.toUpperCase()} ·{' '}
                        {sample.messages.length} lượt trao đổi
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onRunSampleInChat(
                            sample.initialUserPrompt,
                            sample.targetDisease
                          );
                        }}
                        className="flex items-center gap-1 text-xs font-semibold text-teal-700 hover:text-teal-900"
                      >
                        <Play className="h-3 w-3" />
                        <span>Chạy thử</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Detailed Multi-Turn Transcript & Reference Disease Card */}
          <div className="lg:col-span-7 space-y-5">
            <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-5">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-4">
                <div className="space-y-1">
                  <div className="text-xs text-slate-500 font-mono-tabular">
                    <span>MẪU HỘI THOẠI: {selectedSample.conversationId}</span>
                    <span aria-hidden="true"> · </span>
                    <span>CHUYÊN KHOA: {selectedSample.clinicalGroup}</span>
                    <span aria-hidden="true"> · </span>
                    <span>MÃ ICD-10: {selectedSample.icd10}</span>
                  </div>
                  <h3 className="text-base font-bold text-slate-900">
                    Bệnh lý liên quan (target_disease):{' '}
                    {selectedSample.targetDisease}
                  </h3>
                  <p className="text-xs text-slate-600">
                    Hồ sơ giả lập (Persona): {selectedSample.patientPersona}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() =>
                    onRunSampleInChat(
                      selectedSample.initialUserPrompt,
                      selectedSample.targetDisease
                    )
                  }
                  className="flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2.5 text-xs font-semibold text-white hover:bg-teal-700 transition-colors whitespace-nowrap shrink-0"
                >
                  <Play className="h-3.5 w-3.5" />
                  <span>Chạy Thử Kịch Bản Này Trên Chatbot</span>
                </button>
              </div>

              {/* Multi-turn Dialogue Transcript */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-slate-900">
                  Kịch Bản Hội Thoại Thu Thập Triệu Chứng Đa Lượt (Multi-turn History Taking):
                </h4>
                <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
                  {selectedSample.messages.map((turn) => (
                    <div
                      key={turn.turn}
                      className={`rounded-lg p-3.5 text-xs leading-relaxed space-y-1.5 ${
                        turn.role === 'user'
                          ? 'bg-slate-900 text-white ml-4'
                          : 'border border-slate-200 bg-white text-slate-800 mr-4'
                      }`}
                    >
                      <div className="flex items-center justify-between font-mono-tabular text-[11px] opacity-75">
                        <span className="font-semibold">
                          {turn.role === 'user'
                            ? `Lượt ${turn.turn} · Người bệnh mô tả triệu chứng`
                            : `Lượt ${turn.turn} · Trợ lý AI hỏi bổ sung / Phân tích bệnh`}
                        </span>
                        {turn.slotExtracted && <span>{turn.slotExtracted}</span>}
                      </div>
                      <p className="whitespace-pre-line">{turn.content}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Reference Disease Info & Facility Recommendation */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-slate-900">
                    <BookOpen className="h-4 w-4 text-teal-600 shrink-0" />
                    <span>Thông Tin Y Tế Tham Khảo Về Bệnh</span>
                  </div>
                  <p className="text-xs text-slate-700 leading-relaxed">
                    {selectedSample.referenceDiseaseInfo.overview}
                  </p>
                  <div className="pt-1">
                    <span className="text-xs font-semibold text-slate-800 block mb-1">
                      Triệu chứng điển hình:
                    </span>
                    <ul className="space-y-1 text-xs text-slate-600">
                      {selectedSample.referenceDiseaseInfo.typicalSymptoms.map(
                        (sym, idx) => (
                          <li key={idx}>• {sym}</li>
                        )
                      )}
                    </ul>
                  </div>
                </div>

                <div className="rounded-lg border border-teal-200 bg-teal-50/40 p-4 space-y-2.5">
                  <div className="flex items-center gap-2 text-xs font-bold text-teal-950">
                    <Building2 className="h-4 w-4 text-teal-700 shrink-0" />
                    <span>Khuyến Nghị Cơ Sở Y Tế & Thăm Khám Chuyên Môn</span>
                  </div>
                  <div className="text-xs space-y-1.5 text-slate-800">
                    <p>
                      <strong>Cơ sở & Chuyên khoa: </strong>
                      {selectedSample.referenceDiseaseInfo.recommendedFacility}
                    </p>
                    <p>
                      <strong>Thời điểm cần khám: </strong>
                      {selectedSample.referenceDiseaseInfo.whenToSeeDoctor}
                    </p>
                  </div>
                  <div className="pt-1 border-t border-teal-200/70">
                    <span className="text-xs font-bold text-red-800 block mb-1">
                      Dấu hiệu cần đến cơ sở y tế cấp cứu ngay:
                    </span>
                    <ul className="space-y-1 text-xs text-red-900">
                      {selectedSample.referenceDiseaseInfo.redFlags.map(
                        (rf, idx) => (
                          <li key={idx}>• {rf}</li>
                        )
                      )}
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 2: DATASET STATISTICS & LEAKAGE-CONTROLLED PIPELINE */}
      {activeSection === 'overview' && (
        <div className="space-y-6">
          {/* Metric Summary Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-1">
              <span className="text-xs text-slate-500">
                TỔNG HỘI THOẠI GỐC (VIETNAMESE)
              </span>
              <p className="text-2xl font-bold text-slate-900 font-mono-tabular">
                58.064
              </p>
              <p className="text-xs text-slate-500">
                1.236 nhóm bệnh (target_disease) · Trung vị 11–13 lượt
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-1">
              <span className="text-xs text-slate-500">
                TẬP CLEAN STANDARD (E2)
              </span>
              <p className="text-2xl font-bold text-teal-700 font-mono-tabular">
                51.320
              </p>
              <p className="text-xs text-slate-500 font-mono-tabular">
                Train: 41.067 · Val: 5.151 · Test: 5.102
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-1">
              <span className="text-xs text-slate-500">
                TẬP CLEAN STRICT (E3)
              </span>
              <p className="text-2xl font-bold text-slate-900 font-mono-tabular">
                33.237
              </p>
              <p className="text-xs text-slate-500 font-mono-tabular">
                Train: 26.561 · Val: 3.353 · Test: 3.323
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-1">
              <span className="text-xs text-slate-500">
                CHỐNG RÒ RỈ NHÓM BỆNH (SPLIT 80/10/10)
              </span>
              <p className="text-2xl font-bold text-emerald-700 font-mono-tabular">
                0 / 0 / 0
              </p>
              <p className="text-xs text-slate-500">
                Không trùng nhóm bệnh giữa Train, Val và Test
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Rejection Reasons Table */}
            <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
              <div className="border-b border-slate-200 pb-3">
                <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
                  <Database className="h-4 w-4 text-teal-600" />
                  <span>
                    Thống Kê Bộ Lọc Làm Sạch Dữ Liệu (dialogue-clean-v1)
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Loại bỏ các hội thoại lỗi thẻ suy luận, kê liều thuốc nguy
                  hiểm, bỏ sót cấp cứu hoặc đảo vai bác sĩ – bệnh nhân.
                </p>
              </div>

              <div className="space-y-2">
                <span className="text-xs font-bold text-slate-800 block">
                  Lý do loại ở mức Standard (6.744 hội thoại bị loại):
                </span>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-slate-200 text-slate-500">
                        <th className="py-2 pr-3 font-semibold">Mã bộ lọc</th>
                        <th className="py-2 pr-3 font-semibold">Mô tả lỗi an toàn / cấu trúc</th>
                        <th className="py-2 text-right font-semibold">Số lượng</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {MEDDIES_DATASET_METADATA.rejectionReasonsStandard.map(
                        (r) => (
                          <tr key={r.code}>
                            <td className="py-2 pr-3 font-mono-tabular font-semibold text-slate-800">
                              {r.code}
                            </td>
                            <td className="py-2 pr-3 text-slate-600">
                              {r.label}
                            </td>
                            <td className="py-2 text-right font-mono-tabular font-bold text-slate-900">
                              {r.count.toLocaleString('vi-VN')}
                            </td>
                          </tr>
                        )
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Leakage Control & Strict Filtering */}
            <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
              <div className="border-b border-slate-200 pb-3">
                <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
                  <ShieldCheck className="h-4 w-4 text-teal-600" />
                  <span>
                    Kiểm Soát Chống Rò Rỉ Dữ Liệu & Bộ Lọc Strict
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Đảm bảo tập Test đánh giá đúng năng lực hỏi bệnh trên các
                  nhóm bệnh mô hình chưa từng gặp khi huấn luyện.
                </p>
              </div>

              <div className="space-y-3">
                {MEDDIES_DATASET_METADATA.leakageChecks.map((chk, idx) => (
                  <div
                    key={idx}
                    className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-slate-900">
                        {chk.metric}
                      </span>
                      <span className="font-mono-tabular font-bold text-teal-700 shrink-0">
                        {chk.value}
                      </span>
                    </div>
                    <p className="text-slate-500">{chk.status}</p>
                  </div>
                ))}
              </div>

              <div className="pt-2 space-y-2">
                <span className="text-xs font-bold text-slate-800 block">
                  Lý do lọc bổ sung ở mức Strict (Giữ lại 33.237 hội thoại chất lượng cao):
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  {MEDDIES_DATASET_METADATA.rejectionReasonsStrict.map((sr) => (
                    <div
                      key={sr.code}
                      className="rounded border border-slate-200 bg-white p-2.5 flex items-center justify-between gap-2"
                    >
                      <span className="text-slate-600 truncate" title={sr.label}>
                        {sr.label}
                      </span>
                      <span className="font-mono-tabular font-bold text-slate-900 shrink-0">
                        {sr.count.toLocaleString('vi-VN')}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 3: QLORA TRAINING & EVALUATION BENCHMARKS */}
      {activeSection === 'benchmarks' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-3">
              <div>
                <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
                  <Cpu className="h-4 w-4 text-teal-600" />
                  <span>
                    Kết Quả Đánh Giá Thực Nghiệm Hỏi Bệnh Đa Lượt (295 mục Test · Bệnh chưa gặp khi Train)
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Cấu hình: {MEDDIES_BENCHMARK_EXPERIMENTS.hardware} · Ngoặc
                  vuông là khoảng tin cậy 95% Bootstrap theo hội thoại.
                </p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500">
                    <th className="py-2.5 pr-4 font-semibold">Chỉ số đánh giá (Evaluation Metric)</th>
                    <th className="py-2.5 pr-4 font-semibold">E1 (Qwen Gốc)</th>
                    <th className="py-2.5 pr-4 font-semibold text-teal-800">
                      E2 (LoRA Standard)
                    </th>
                    <th className="py-2.5 pr-4 font-semibold">E3 (LoRA Strict)</th>
                    <th className="py-2.5 pr-4 font-semibold">P0 (Question Planner)</th>
                    <th className="py-2.5 font-semibold">Ý nghĩa thực nghiệm</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {MEDDIES_BENCHMARK_EXPERIMENTS.metricsTable.map((row, i) => (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="py-3 pr-4 font-semibold text-slate-900">
                        {row.metric}
                      </td>
                      <td className="py-3 pr-4 font-mono-tabular text-slate-600">
                        {row.e1Base}
                      </td>
                      <td className="py-3 pr-4 font-mono-tabular font-bold text-teal-700">
                        {row.e2Standard}
                      </td>
                      <td className="py-3 pr-4 font-mono-tabular text-slate-800">
                        {row.e3Strict}
                      </td>
                      <td className="py-3 pr-4 font-mono-tabular font-bold text-slate-900">
                        {row.p0Planner}
                      </td>
                      <td className="py-3 text-slate-600">{row.highlight}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Validation Loss Progression & Safety Evaluation */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
              <div className="border-b border-slate-200 pb-3">
                <h3 className="text-sm font-bold text-slate-900">
                  Sự Hội Tụ Validation Loss Khi Fine-Tune QLoRA (E2 & E3 so với Base E1)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Đo trên cùng 80 hội thoại Validation (100 cửa sổ ngữ cảnh ≤ 2.048 token).
                </p>
              </div>

              <div className="space-y-3">
                {MEDDIES_BENCHMARK_EXPERIMENTS.valLossCurve.map((pt, idx) => (
                  <div key={idx} className="space-y-1 text-xs">
                    <div className="flex items-center justify-between font-mono-tabular">
                      <span className="font-semibold text-slate-800">
                        {pt.step}
                      </span>
                      <span className="text-slate-600">
                        E1 Base: {pt.e1Base.toFixed(3)} ·{' '}
                        <strong className="text-teal-700">
                          E2 LoRA: {pt.e2Standard.toFixed(3)}
                        </strong>{' '}
                        · E3 Strict: {pt.e3Strict.toFixed(3)}
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className="h-full bg-teal-600 rounded-full transition-all"
                        style={{
                          width: `${Math.max(
                            25,
                            Math.min(100, (pt.e2Standard / 2.4) * 100)
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
              <div className="border-b border-slate-200 pb-3">
                <h3 className="text-sm font-bold text-slate-900">
                  Kiểm Thử Lớp An Toàn Y Khoa & Dialogue State Tracker (DST)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Đảm bảo hệ thống không bao giờ bỏ sót ca cấp cứu hoặc trả lời ngoài phạm vi y tế.
                </p>
              </div>

              <div className="space-y-3">
                {MEDDIES_BENCHMARK_EXPERIMENTS.safetySuiteResults.map(
                  (item, idx) => (
                    <div
                      key={idx}
                      className="rounded-lg border border-slate-200 bg-slate-50 p-3.5 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-bold text-slate-900">
                          {item.component}
                        </span>
                        <span className="font-mono-tabular font-bold text-emerald-700">
                          {item.result}
                        </span>
                      </div>
                      <p className="text-slate-600">Bộ kiểm thử: {item.dataset}</p>
                    </div>
                  )
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

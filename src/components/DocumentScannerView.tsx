import React, { useState, useRef } from 'react';
import {
  FileText,
  Upload,
  CheckCircle2,
  AlertTriangle,
  Plus,
  Sparkles,
  FileSearch,
  Clock,
  HelpCircle,
} from 'lucide-react';
import {
  DocumentAnalysisResult,
  ExtractedMedicationItem,
  MedicationSlot,
  PatientProfile,
} from '../types/health';
import { SAMPLE_DOCUMENTS_PRESETS } from '../data/defaultHealthData';
import { processUploadedImage } from '../utils/imageHelper';

interface DocumentScannerViewProps {
  history: DocumentAnalysisResult[];
  onSaveAnalysis: (result: DocumentAnalysisResult) => void;
  patientProfile: PatientProfile;
  onAddMedicationToProfile: (med: {
    name: string;
    dosage: string;
    frequency: string;
    slots: MedicationSlot[];
    instructions: string;
    purpose: string;
  }) => void;
}

export const DocumentScannerView: React.FC<DocumentScannerViewProps> = ({
  history,
  onSaveAnalysis,
  patientProfile,
  onAddMedicationToProfile,
}) => {
  const [selectedDocType, setSelectedDocType] = useState<string>('AUTO');
  const [customText, setCustomText] = useState<string>('');
  const [uploadedImage, setUploadedImage] = useState<{
    base64Data: string;
    mimeType: string;
    previewUrl: string;
    fileName: string;
  } | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [activeResult, setActiveResult] = useState<DocumentAnalysisResult | null>(
    history[0] || null
  );
  const [addedMedKeys, setAddedMedKeys] = useState<Record<string, boolean>>({});

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setErrorMsg(null);
    try {
      const processed = await processUploadedImage(file);
      setUploadedImage({
        ...processed,
        fileName: file.name,
      });
    } catch (err: any) {
      setErrorMsg(err?.message || 'Không thể xử lý tệp hình ảnh.');
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const runAnalysis = async (presetText?: string, presetType?: string) => {
    const textToUse = presetText !== undefined ? presetText : customText.trim();
    const docTypeToUse = presetType !== undefined ? presetType : selectedDocType;

    if (!uploadedImage && !textToUse) {
      setErrorMsg(
        'Vui lòng tải lên ảnh chụp đơn thuốc / phiếu xét nghiệm hoặc chọn một mẫu có sẵn để phân tích.'
      );
      return;
    }

    setErrorMsg(null);
    setIsAnalyzing(true);

    try {
      const response = await fetch('/api/health/analyze-doc', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          imageBase64: presetText ? undefined : uploadedImage?.base64Data,
          imageMimeType: presetText ? undefined : uploadedImage?.mimeType,
          textContext: textToUse,
          docType: docTypeToUse,
          patientProfile,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Không thể phân tích tài liệu lúc này.');
      }

      const resultObj: DocumentAnalysisResult = {
        id: `doc-${Date.now()}`,
        analyzedAt: new Date().toLocaleString('vi-VN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
        }),
        detectedType: data.detectedType || 'LAB_RESULT',
        title: data.title || 'Kết quả Phân tích Cận lâm sàng & Đơn thuốc',
        overallSummary: data.overallSummary || '',
        triageStatus: data.triageStatus || 'ATTENTION',
        metrics: Array.isArray(data.metrics) ? data.metrics : [],
        extractedMedications: Array.isArray(data.extractedMedications)
          ? data.extractedMedications
          : [],
        recommendations: Array.isArray(data.recommendations)
          ? data.recommendations
          : [],
        questionsForDoctor: Array.isArray(data.questionsForDoctor)
          ? data.questionsForDoctor
          : [],
        imagePreviewUrl: presetText ? undefined : uploadedImage?.previewUrl,
      };

      onSaveAnalysis(resultObj);
      setActiveResult(resultObj);
    } catch (err: any) {
      setErrorMsg(
        err?.message || 'Đã xảy ra lỗi khi đọc tài liệu y tế. Vui lòng thử lại.'
      );
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleSaveExtractedMed = (med: ExtractedMedicationItem, index: number) => {
    const validSlots: MedicationSlot[] = ['Sáng', 'Trưa', 'Chiều', 'Tối'];
    const filteredSlots = (med.timing || []).filter((t): t is MedicationSlot =>
      validSlots.includes(t as MedicationSlot)
    );
    onAddMedicationToProfile({
      name: med.name,
      dosage: med.dosage,
      frequency: med.frequency,
      slots: filteredSlots.length > 0 ? filteredSlots : ['Sáng'],
      instructions: med.instructions,
      purpose: med.purpose,
    });
    setAddedMedKeys((prev) => ({
      ...prev,
      [`${activeResult?.id}-${index}`]: true,
    }));
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      {/* Left Column: Upload & Clinical Sample Presets */}
      <div className="lg:col-span-5 space-y-5">
        <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
          <div>
            <h2 className="text-base font-bold text-slate-900">
              Đọc & Giải Thích Đơn Thuốc / Xét Nghiệm (OCR)
            </h2>
            <p className="text-xs text-slate-600 mt-1 leading-relaxed">
              Tải lên hình ảnh đơn thuốc hoặc phiếu xét nghiệm máu/sinh hóa. AI sẽ bóc tách từng chỉ số, đối chiếu ngưỡng bình thường và kiểm tra dị ứng thuốc tự động.
            </p>
          </div>

          {/* Document Type Segmented Filter */}
          <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-1">
            {[
              { id: 'AUTO', label: 'Tự nhận diện' },
              { id: 'LAB_RESULT', label: 'Phiếu xét nghiệm' },
              { id: 'PRESCRIPTION', label: 'Đơn thuốc' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setSelectedDocType(tab.id)}
                className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors whitespace-nowrap shrink-0 ${
                  selectedDocType === tab.id
                    ? 'bg-white text-slate-900 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Upload Dropzone */}
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-center space-y-3">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileChange}
              className="hidden"
            />
            {uploadedImage ? (
              <div className="space-y-3">
                <img
                  src={uploadedImage.previewUrl}
                  alt="Ảnh tài liệu y tế"
                  referrerPolicy="no-referrer"
                  className="mx-auto max-h-48 rounded-lg border border-slate-200 object-contain bg-white"
                />
                <p className="text-xs font-medium text-slate-700 truncate">
                  {uploadedImage.fileName}
                </p>
                <div className="flex justify-center gap-2">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
                  >
                    Đổi ảnh khác
                  </button>
                  <button
                    type="button"
                    onClick={() => setUploadedImage(null)}
                    className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100"
                  >
                    Xóa ảnh
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-2.5">
                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50 text-teal-600">
                  <Upload className="h-5 w-5" />
                </div>
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-slate-800">
                    Chụp hoặc tải ảnh Đơn thuốc / Kết quả xét nghiệm
                  </p>
                  <p className="text-xs text-slate-500">
                    Hỗ trợ JPG, PNG rõ chữ (Tự động tối ưu dung lượng ảnh)
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-white border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-100 transition-colors"
                >
                  <Upload className="h-3.5 w-3.5 text-teal-600" />
                  <span>Chọn Ảnh Từ Thiết Bị</span>
                </button>
              </div>
            )}
          </div>

          {/* Optional Text / Clinical Note Input */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 block">
              Hoặc dán nội dung chỉ số xét nghiệm / tên thuốc vào đây:
            </label>
            <textarea
              rows={3}
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              placeholder="Ví dụ: Glucose lúc đói 6.4 mmol/L, HbA1c 6.1%, Triglyceride 2.5 mmol/L..."
              className="w-full rounded-lg border border-slate-300 bg-white p-3 text-xs text-slate-900 placeholder:text-slate-400 focus:border-teal-600 focus:outline-none"
            />
          </div>

          <button
            type="button"
            disabled={isAnalyzing}
            onClick={() => runAnalysis()}
            className="w-full flex items-center justify-center gap-2 rounded-lg bg-teal-600 px-4 py-2.5 text-xs font-semibold text-white hover:bg-teal-700 transition-colors disabled:opacity-50"
          >
            <FileSearch className="h-4 w-4" />
            <span>
              {isAnalyzing
                ? 'Đang bóc tách chỉ số & đối chiếu hồ sơ...'
                : 'Phân Tích Tài Liệu Y Tế Ngay'}
            </span>
          </button>

          {errorMsg && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800">
              {errorMsg}
            </div>
          )}
        </div>

        {/* Built-in Clinical Sample Presets for Instant Testing */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Dữ Liệu Mẫu Lâm Sàng (Chạy Thử 1-Chạm)
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Bấm vào mẫu dưới đây để nạp dữ liệu và chạy AI phân tích trực tiếp:
            </p>
          </div>

          <div className="space-y-2.5">
            {SAMPLE_DOCUMENTS_PRESETS.map((sample) => (
              <div
                key={sample.id}
                className="rounded-lg border border-slate-200 bg-slate-50/70 p-3.5 space-y-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold text-slate-900">
                    {sample.label}
                  </span>
                  <button
                    disabled={isAnalyzing}
                    onClick={() => {
                      setCustomText(sample.textContext);
                      setSelectedDocType(sample.docType);
                      runAnalysis(sample.textContext, sample.docType);
                    }}
                    className="inline-flex items-center gap-1 rounded-md bg-slate-900 px-2.5 py-1 text-xs font-medium text-white hover:bg-slate-800 transition-colors whitespace-nowrap shrink-0 disabled:opacity-50"
                  >
                    <Sparkles className="h-3 w-3" />
                    <span>Phân tích mẫu này</span>
                  </button>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {sample.description}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Saved Document History */}
        {history.length > 0 && (
          <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3">
            <h3 className="text-sm font-bold text-slate-900">
              Lịch Sử Phiếu Đã Phân Tích ({history.length})
            </h3>
            <div className="space-y-2 max-h-56 overflow-y-auto">
              {history.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setActiveResult(item)}
                  className={`w-full text-left rounded-lg border p-3 transition-colors ${
                    activeResult?.id === item.id
                      ? 'border-teal-600 bg-teal-50/40'
                      : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                >
                  <p className="text-xs font-semibold text-slate-900 truncate">
                    {item.title}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5 font-mono-tabular">
                    <span>{item.detectedType}</span>
                    <span aria-hidden="true"> · </span>
                    <span>{item.analyzedAt}</span>
                  </p>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Right Column: Detailed Structured Report */}
      <div className="lg:col-span-7">
        {isAnalyzing ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-4 animate-pulse">
            <div className="h-6 w-2/3 rounded bg-slate-200" />
            <div className="h-4 w-full rounded bg-slate-200" />
            <div className="h-4 w-5/6 rounded bg-slate-200" />
            <div className="h-48 w-full rounded-lg bg-slate-100 mt-4" />
            <p className="text-xs font-medium text-teal-700">
              AI đang trích xuất bảng chỉ số cận lâm sàng và kiểm tra chéo với tiền sử dị ứng ({patientProfile.allergies.join(', ')})...
            </p>
          </div>
        ) : activeResult ? (
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden space-y-6 p-6">
            {/* Report Header */}
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-xs text-slate-500 font-mono-tabular">
                  <span>Loại phiếu: {activeResult.detectedType}</span>
                  <span aria-hidden="true">·</span>
                  <span>Thời gian: {activeResult.analyzedAt}</span>
                  <span aria-hidden="true">·</span>
                  <span
                    className={`font-bold ${
                      activeResult.triageStatus === 'CRITICAL'
                        ? 'text-red-600'
                        : activeResult.triageStatus === 'ATTENTION'
                        ? 'text-amber-600'
                        : 'text-emerald-600'
                    }`}
                  >
                    Đánh giá: {activeResult.triageStatus}
                  </span>
                </div>
                <h3 className="text-lg font-bold text-slate-900">
                  {activeResult.title}
                </h3>
              </div>
            </div>

            {/* Overall Clinical Summary */}
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-1.5">
              <span className="text-xs font-bold text-slate-900 block">
                Tóm tắt Kết quả & Nhận định Lâm sàng
              </span>
              <p className="text-sm text-slate-700 leading-relaxed">
                {activeResult.overallSummary}
              </p>
            </div>

            {/* Lab Metrics Table */}
            {activeResult.metrics.length > 0 && (
              <div className="space-y-3">
                <h4 className="text-sm font-bold text-slate-900">
                  Bảng Phân Tích Chỉ Số Cận Lâm Sàng ({activeResult.metrics.length} chỉ số)
                </h4>
                <div className="overflow-x-auto rounded-lg border border-slate-200">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold text-slate-600">
                        <th className="py-2.5 px-3.5">Tên chỉ số</th>
                        <th className="py-2.5 px-3.5 text-right">Kết quả</th>
                        <th className="py-2.5 px-3.5 text-right">Tham chiếu</th>
                        <th className="py-2.5 px-3.5">Đánh giá</th>
                        <th className="py-2.5 px-3.5">Giải thích ý nghĩa</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 text-xs">
                      {activeResult.metrics.map((m, idx) => (
                        <tr key={idx} className="hover:bg-slate-50/80">
                          <td className="py-3 px-3.5 font-semibold text-slate-900">
                            {m.name}
                          </td>
                          <td className="py-3 px-3.5 text-right font-mono-tabular font-bold text-slate-900 whitespace-nowrap">
                            {m.value} <span className="font-normal text-slate-500">{m.unit}</span>
                          </td>
                          <td className="py-3 px-3.5 text-right font-mono-tabular text-slate-600 whitespace-nowrap">
                            {m.referenceRange}
                          </td>
                          <td className="py-3 px-3.5 whitespace-nowrap">
                            {m.status === 'HIGH' && (
                              <span className="font-semibold text-amber-700">
                                ↑ Cao hơn chuẩn
                              </span>
                            )}
                            {m.status === 'LOW' && (
                              <span className="font-semibold text-amber-700">
                                ↓ Thấp hơn chuẩn
                              </span>
                            )}
                            {m.status === 'NORMAL' && (
                              <span className="font-semibold text-emerald-700">
                                ✓ Bình thường
                              </span>
                            )}
                            {m.status === 'INFO' && (
                              <span className="text-slate-600">Thông tin</span>
                            )}
                          </td>
                          <td className="py-3 px-3.5 text-slate-700 leading-relaxed min-w-[220px]">
                            {m.explanation}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Extracted Prescription Medications */}
            {activeResult.extractedMedications.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-bold text-slate-900">
                    Danh Sách Thuốc Bóc Tách Từ Đơn ({activeResult.extractedMedications.length} thuốc)
                  </h4>
                  <span className="text-xs text-slate-500">
                    Bấm "Lưu lịch nhắc" để thêm thẳng vào Hồ sơ uống thuốc
                  </span>
                </div>

                <div className="space-y-3">
                  {activeResult.extractedMedications.map((med, idx) => {
                    const isSaved =
                      addedMedKeys[`${activeResult.id}-${idx}`] || false;
                    return (
                      <div
                        key={idx}
                        className={`rounded-lg border p-4 space-y-2.5 ${
                          med.allergyWarning
                            ? 'border-red-300 bg-red-50/50'
                            : 'border-slate-200 bg-white'
                        }`}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <h5 className="text-sm font-bold text-slate-900">
                              {med.name}
                            </h5>
                            <p className="text-xs text-slate-600 font-mono-tabular mt-0.5">
                              <span>Liều: {med.dosage}</span>
                              <span aria-hidden="true"> · </span>
                              <span>Tần suất: {med.frequency}</span>
                              <span aria-hidden="true"> · </span>
                              <span>
                                Buổi: {(med.timing || []).join(', ') || 'Theo chỉ định'}
                              </span>
                            </p>
                          </div>

                          <button
                            type="button"
                            disabled={isSaved}
                            onClick={() => handleSaveExtractedMed(med, idx)}
                            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors whitespace-nowrap shrink-0 ${
                              isSaved
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-teal-600 text-white hover:bg-teal-700'
                            }`}
                          >
                            {isSaved ? (
                              <>
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                <span>Đã lưu vào Lịch thuốc</span>
                              </>
                            ) : (
                              <>
                                <Plus className="h-3.5 w-3.5" />
                                <span>Lưu vào Lịch nhắc thuốc</span>
                              </>
                            )}
                          </button>
                        </div>

                        <p className="text-xs text-slate-700">
                          <strong className="text-slate-900">Công dụng: </strong>
                          {med.purpose} —{' '}
                          <strong className="text-slate-900">Cách uống: </strong>
                          {med.instructions}
                        </p>

                        {med.allergyWarning && (
                          <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-100/70 p-2.5 text-xs text-red-900">
                            <AlertTriangle className="h-4 w-4 text-red-600 shrink-0 mt-0.5" />
                            <div>
                              <strong className="font-bold">
                                Cảnh báo Dị ứng / Bệnh nền:{' '}
                              </strong>
                              <span>{med.allergyWarning}</span>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Recommendations & Questions for Doctor */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {activeResult.recommendations.length > 0 && (
                <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4 space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-900">
                    <Clock className="h-4 w-4 text-teal-600" />
                    <span>Khuyến nghị Dinh dưỡng & Theo dõi</span>
                  </div>
                  <ul className="space-y-1.5 text-xs text-slate-700 leading-relaxed">
                    {activeResult.recommendations.map((rec, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="font-mono-tabular font-semibold text-teal-700 shrink-0">
                          0{i + 1}.
                        </span>
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {activeResult.questionsForDoctor.length > 0 && (
                <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4 space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-900">
                    <HelpCircle className="h-4 w-4 text-teal-600" />
                    <span>Câu hỏi nên trao đổi với Bác sĩ điều trị</span>
                  </div>
                  <ul className="space-y-1.5 text-xs text-slate-700 leading-relaxed">
                    {activeResult.questionsForDoctor.map((q, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="font-mono-tabular font-semibold text-slate-500 shrink-0">
                          0{i + 1}.
                        </span>
                        <span>{q}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-slate-200 bg-white p-10 text-center space-y-3">
            <FileText className="mx-auto h-8 w-8 text-slate-400" />
            <h3 className="text-base font-bold text-slate-900">
              Chưa có tài liệu nào được chọn
            </h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Hãy tải lên ảnh chụp đơn thuốc, phiếu xét nghiệm máu hoặc chọn một mẫu lâm sàng bên trái để xem báo cáo phân tích chi tiết.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

import React, { useState } from 'react';
import {
  Pill,
  Plus,
  X,
  ShieldCheck,
  AlertTriangle,
  AlertOctagon,
  Search,
  Sparkles,
  CheckCircle2,
} from 'lucide-react';
import { DrugInteractionResult, PatientProfile } from '../types/health';

interface DrugInteractionViewProps {
  patientProfile: PatientProfile;
}

const PRESET_DRUG_COMBOS = [
  {
    label: 'Kiểm tra Ibuprofen + Aspirin + Esomeprazole',
    drugs: ['Ibuprofen 400mg', 'Aspirin 81mg', 'Esomeprazole 20mg'],
    question:
      'Tôi bị đau khớp gối định uống Ibuprofen cùng với Aspirin và thuốc dạ dày Esomeprazole đang dùng có an toàn không?',
  },
  {
    label: 'Kiểm tra kháng sinh Augmentin 1g + Paracetamol 500mg',
    drugs: ['Augmentin 1g (Amoxicillin + Clavulanat)', 'Paracetamol 500mg'],
    question:
      'Kiểm tra giúp tôi đơn thuốc này có xung đột với tiền sử dị ứng Penicillin trong hồ sơ của tôi không?',
  },
  {
    label: 'Kiểm tra Amlodipine 5mg + Simvastatin 20mg + Omega-3',
    drugs: ['Amlodipine 5mg', 'Simvastatin 20mg', 'Omega-3 Fish Oil 1000mg'],
    question:
      'Tôi dùng thuốc huyết áp Amlodipine cùng thuốc mỡ máu Simvastatin và Omega-3 thì nên chia giờ uống sáng tối thế nào?',
  },
];

const INITIAL_INTERACTION_RESULT: DrugInteractionResult = {
  overallSafety: 'CONTRAINDICATED',
  safetyHeadline:
    'Cảnh báo Nghiêm trọng: Phối hợp Ibuprofen + Aspirin làm tăng mạnh nguy cơ xuất huyết dạ dày và giảm hiệu quả bảo vệ tim mạch',
  summary:
    'Việc dùng đồng thời hai thuốc thuộc nhóm kháng viêm không steroid (Ibuprofen và Aspirin) trên bệnh nhân có tiền sử Viêm dạ dày tá tràng gây nguy cơ loét và xuất huyết tiêu hóa rất cao. Ngoài ra, Ibuprofen cạnh tranh gắn kết làm mất tác dụng chống kết tập tiểu cầu của Aspirin liều thấp.',
  pairInteractions: [
    {
      pair: 'Ibuprofen 400mg + Aspirin 81mg',
      severity: 'SEVERE',
      mechanism:
        'Cả hai đều là thuốc kháng viêm NSAID ức chế COX-1, gây hiệp đồng độc tính trên niêm mạc dạ dày tá tràng và làm tăng nguy cơ chảy máu.',
      recommendation:
        'Tránh tự ý phối hợp. Nếu cần giảm đau thông thường, ưu tiên đổi sang Paracetamol 500mg (an toàn hơn cho dạ dày) sau khi hỏi ý kiến bác sĩ.',
    },
    {
      pair: 'Esomeprazole 20mg + Nhóm NSAID',
      severity: 'NONE',
      mechanism:
        'Esomeprazole giảm tiết axit dịch vị, hỗ trợ bảo vệ dạ dày nhưng không loại bỏ hoàn toàn nguy cơ xuất huyết nếu dùng kép 2 thuốc NSAID.',
      recommendation:
        'Tiếp tục uống Esomeprazole 20mg trước ăn sáng 30 phút.',
    },
  ],
  profileAlerts: [
    'Tiền sử bệnh nền: Hồ sơ ghi nhận bạn có Viêm dạ dày tá tràng nhẹ — Ibuprofen và Aspirin đều chống chỉ định tương đối hoặc cần giám sát y tế chặt chẽ.',
    'Tiền sử dị ứng: Các thuốc đang kiểm tra không thuộc nhóm kháng sinh Beta-lactam/Penicillin.',
  ],
  medicationProfiles: [
    {
      name: 'Ibuprofen 400mg',
      activeIngredient: 'Ibuprofen (Nhóm kháng viêm không steroid - NSAID)',
      mainUse: 'Giảm đau, hạ sốt, kháng viêm cơ xương khớp',
      bestTiming: 'Uống ngay sau khi ăn no để giảm kích ứng niêm mạc dạ dày',
      commonSideEffects: [
        'Đau rát thượng vị, ợ chua, buồn nôn',
        'Tăng nguy cơ viêm loét và xuất huyết tiêu hóa',
        'Giữ nước, tăng nhẹ huyết áp',
      ],
      foodInteractions:
        'Tuyệt đối không uống cùng rượu bia hoặc khi bụng đói vì làm tăng gấp 3 lần nguy cơ chảy máu dạ dày.',
    },
    {
      name: 'Esomeprazole 20mg',
      activeIngredient: 'Esomeprazole (Nhóm ức chế bơm proton - PPI)',
      mainUse: 'Điều trị trào ngược dạ dày thực quản (GERD) và viêm loét dạ dày tá tràng',
      bestTiming: 'Uống nguyên viên trước bữa ăn sáng 30 - 60 phút',
      commonSideEffects: ['Đầy hơi nhẹ, nhức đầu thoáng qua'],
      foodInteractions:
        'Không nhai hoặc nghiền nát viên thuốc (vì làm hỏng lớp bao tan trong ruột).',
    },
  ],
};

export const DrugInteractionView: React.FC<DrugInteractionViewProps> = ({
  patientProfile,
}) => {
  const [drugList, setDrugList] = useState<string[]>([
    'Ibuprofen 400mg',
    'Aspirin 81mg',
    'Esomeprazole 20mg',
  ]);
  const [newDrugInput, setNewDrugInput] = useState('');
  const [questionInput, setQuestionInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<DrugInteractionResult | null>(
    INITIAL_INTERACTION_RESULT
  );

  const handleAddDrug = () => {
    const trimmed = newDrugInput.trim();
    if (!trimmed) return;
    if (!drugList.includes(trimmed)) {
      setDrugList((prev) => [...prev, trimmed]);
    }
    setNewDrugInput('');
  };

  const handleRemoveDrug = (drugToRemove: string) => {
    setDrugList((prev) => prev.filter((d) => d !== drugToRemove));
  };

  const handleLoadProfileMeds = () => {
    const profileMedNames = patientProfile.medications.map((m) => m.name);
    const merged = Array.from(new Set([...drugList, ...profileMedNames]));
    setDrugList(merged);
  };

  const runInteractionCheck = async (
    overrideDrugs?: string[],
    overrideQuestion?: string
  ) => {
    const targetDrugs = overrideDrugs || drugList;
    const targetQuestion =
      overrideQuestion !== undefined ? overrideQuestion : questionInput.trim();

    if (targetDrugs.length === 0) {
      setErrorMsg('Vui lòng thêm ít nhất 1 loại thuốc vào danh sách kiểm tra.');
      return;
    }

    setErrorMsg(null);
    setIsLoading(true);

    try {
      const response = await fetch('/api/health/interactions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          medications: targetDrugs,
          patientProfile,
          question: targetQuestion,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(
          data.error || 'Không thể kiểm tra tương tác thuốc lúc này.'
        );
      }

      setResult({
        overallSafety: data.overallSafety || 'CAUTION',
        safetyHeadline:
          data.safetyHeadline || 'Kết quả phân tích tương tác dược lâm sàng',
        summary: data.summary || '',
        pairInteractions: Array.isArray(data.pairInteractions)
          ? data.pairInteractions
          : [],
        profileAlerts: Array.isArray(data.profileAlerts)
          ? data.profileAlerts
          : [],
        medicationProfiles: Array.isArray(data.medicationProfiles)
          ? data.medicationProfiles
          : [],
      });
    } catch (err: any) {
      setErrorMsg(
        err?.message || 'Đã xảy ra lỗi khi phân tích tương tác thuốc.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      {/* Left Column: Drug List Builder & Presets */}
      <div className="lg:col-span-5 space-y-5">
        <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
          <div>
            <h2 className="text-base font-bold text-slate-900">
              Tra Cứu Thuốc & Kiểm Tra Tương Tác An Toàn
            </h2>
            <p className="text-xs text-slate-600 mt-1 leading-relaxed">
              Kiểm tra xung đột hoạt chất giữa các loại thuốc, thực phẩm chức năng và tự động đối chiếu với tiền sử dị ứng ({patientProfile.allergies.join(', ') || 'Không có'}) cũng như bệnh nền của bạn.
            </p>
          </div>

          {/* Add Medication Input */}
          <div className="flex gap-2">
            <input
              type="text"
              value={newDrugInput}
              onChange={(e) => setNewDrugInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleAddDrug();
                }
              }}
              placeholder="Nhập tên thuốc hoặc hoạt chất (VD: Paracetamol 500mg)..."
              className="flex-1 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs text-slate-900 placeholder:text-slate-400 focus:border-teal-600 focus:outline-none"
            />
            <button
              type="button"
              onClick={handleAddDrug}
              className="flex items-center gap-1.5 rounded-lg bg-slate-900 px-3.5 py-2 text-xs font-semibold text-white hover:bg-slate-800 transition-colors whitespace-nowrap shrink-0"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Thêm thuốc</span>
            </button>
          </div>

          {/* Quick Sync from Patient Profile */}
          <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3.5 py-2.5">
            <span className="text-xs text-slate-600">
              Thuốc định kỳ trong hồ sơ ({patientProfile.medications.length} thuốc)
            </span>
            <button
              type="button"
              onClick={handleLoadProfileMeds}
              className="text-xs font-semibold text-teal-700 hover:text-teal-800 whitespace-nowrap shrink-0"
            >
              + Nạp tất cả từ Hồ sơ
            </button>
          </div>

          {/* Active Drug List */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-700">
                Danh sách thuốc đang kiểm tra ({drugList.length}):
              </span>
              {drugList.length > 0 && (
                <button
                  type="button"
                  onClick={() => setDrugList([])}
                  className="text-slate-500 hover:text-red-600"
                >
                  Xóa hết
                </button>
              )}
            </div>

            {drugList.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-300 p-4 text-center text-xs text-slate-500">
                Chưa có thuốc nào trong danh sách. Hãy nhập tên thuốc ở trên hoặc bấm nạp từ Hồ sơ.
              </div>
            ) : (
              <div className="space-y-1.5">
                {drugList.map((drug, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50/70 px-3.5 py-2 text-xs"
                  >
                    <div className="flex items-center gap-2 font-medium text-slate-900">
                      <span className="font-mono-tabular text-slate-400">
                        0{idx + 1}.
                      </span>
                      <span>{drug}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveDrug(drug)}
                      className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
                      aria-label={`Xóa ${drug}`}
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Specific Question */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 block">
              Câu hỏi cụ thể về cách dùng thuốc (tùy chọn):
            </label>
            <input
              type="text"
              value={questionInput}
              onChange={(e) => setQuestionInput(e.target.value)}
              placeholder="VD: Các thuốc này uống cùng lúc sau ăn sáng được không?"
              className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs text-slate-900 placeholder:text-slate-400 focus:border-teal-600 focus:outline-none"
            />
          </div>

          <button
            type="button"
            disabled={isLoading || drugList.length === 0}
            onClick={() => runInteractionCheck()}
            className="w-full flex items-center justify-center gap-2 rounded-lg bg-teal-600 px-4 py-2.5 text-xs font-semibold text-white hover:bg-teal-700 transition-colors disabled:opacity-50"
          >
            <Search className="h-4 w-4" />
            <span>
              {isLoading
                ? 'Đang phân tích dược động học & tương tác...'
                : 'Kiểm Tra Tương Tác & Độ An Toàn'}
            </span>
          </button>

          {errorMsg && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800">
              {errorMsg}
            </div>
          )}
        </div>

        {/* Preset Drug Combos */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3">
          <h3 className="text-sm font-bold text-slate-900">
            Tình Huống Tương Tác Thuốc Phổ Biến (Chạy Thử Nhanh)
          </h3>
          <div className="space-y-2">
            {PRESET_DRUG_COMBOS.map((combo, idx) => (
              <div
                key={idx}
                className="rounded-lg border border-slate-200 bg-slate-50/70 p-3.5 space-y-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold text-slate-900">
                    {combo.label}
                  </span>
                  <button
                    disabled={isLoading}
                    onClick={() => {
                      setDrugList(combo.drugs);
                      setQuestionInput(combo.question);
                      runInteractionCheck(combo.drugs, combo.question);
                    }}
                    className="inline-flex items-center gap-1 rounded-md bg-slate-900 px-2.5 py-1 text-xs font-medium text-white hover:bg-slate-800 transition-colors whitespace-nowrap shrink-0 disabled:opacity-50"
                  >
                    <Sparkles className="h-3 w-3" />
                    <span>Kiểm tra</span>
                  </button>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {combo.question}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right Column: Interaction Matrix & Pharmacology Profiles */}
      <div className="lg:col-span-7">
        {isLoading ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-4 animate-pulse">
            <div className="h-6 w-3/4 rounded bg-slate-200" />
            <div className="h-4 w-full rounded bg-slate-200" />
            <div className="h-32 w-full rounded-lg bg-slate-100" />
            <div className="h-32 w-full rounded-lg bg-slate-100" />
            <p className="text-xs font-medium text-teal-700">
              Dược sĩ AI đang kiểm tra cơ chế tương tác thuốc - thuốc và đối chiếu tiền sử dị ứng...
            </p>
          </div>
        ) : result ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-6">
            {/* Safety Status Banner */}
            <div
              className={`rounded-xl border p-4 space-y-2 ${
                result.overallSafety === 'CONTRAINDICATED'
                  ? 'border-red-300 bg-red-50/80 text-red-950'
                  : result.overallSafety === 'CAUTION'
                  ? 'border-amber-300 bg-amber-50/80 text-amber-950'
                  : 'border-emerald-300 bg-emerald-50/80 text-emerald-950'
              }`}
            >
              <div className="flex items-center gap-2 text-xs font-bold">
                {result.overallSafety === 'CONTRAINDICATED' ? (
                  <AlertOctagon className="h-4 w-4 text-red-600 shrink-0" />
                ) : result.overallSafety === 'CAUTION' ? (
                  <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                ) : (
                  <ShieldCheck className="h-4 w-4 text-emerald-600 shrink-0" />
                )}
                <span>
                  MỨC ĐỘ AN TOÀN DƯỢC LÂM SÀNG: {result.overallSafety}
                </span>
              </div>
              <h3 className="text-base font-bold">{result.safetyHeadline}</h3>
              <p className="text-xs leading-relaxed opacity-90">
                {result.summary}
              </p>
            </div>

            {/* Patient Profile Contraindication Alerts */}
            {result.profileAlerts.length > 0 && (
              <div className="rounded-lg border border-teal-200 bg-teal-50/50 p-4 space-y-2">
                <h4 className="text-xs font-bold text-teal-950">
                  Đối chiếu Cá nhân hóa với Hồ sơ của {patientProfile.fullName}
                </h4>
                <ul className="space-y-1.5 text-xs text-slate-800 leading-relaxed">
                  {result.profileAlerts.map((alert, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="font-mono-tabular font-semibold text-teal-700 shrink-0">
                        0{i + 1}.
                      </span>
                      <span>{alert}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Pairwise Drug Interactions */}
            {result.pairInteractions.length > 0 && (
              <div className="space-y-3">
                <h4 className="text-sm font-bold text-slate-900">
                  Phân Tích Chi Tiết Các Cặp Phối Hợp Thuốc
                </h4>
                <div className="space-y-3">
                  {result.pairInteractions.map((pair, idx) => (
                    <div
                      key={idx}
                      className="rounded-lg border border-slate-200 bg-slate-50/60 p-4 space-y-2"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-sm font-bold text-slate-900">
                          {pair.pair}
                        </span>
                        <span
                          className={`text-xs font-bold font-mono-tabular ${
                            pair.severity === 'SEVERE'
                              ? 'text-red-600'
                              : pair.severity === 'MODERATE'
                              ? 'text-amber-600'
                              : pair.severity === 'MILD'
                              ? 'text-teal-700'
                              : 'text-emerald-700'
                          }`}
                        >
                          Mức độ tương tác: {pair.severity}
                        </span>
                      </div>
                      <p className="text-xs text-slate-700 leading-relaxed">
                        <strong className="text-slate-900">Cơ chế: </strong>
                        {pair.mechanism}
                      </p>
                      <p className="text-xs text-teal-900 font-medium leading-relaxed">
                        <strong className="text-slate-900">Khuyến nghị xử trí: </strong>
                        {pair.recommendation}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Detailed Medication Pharmacology Cards */}
            {result.medicationProfiles.length > 0 && (
              <div className="space-y-3">
                <h4 className="text-sm font-bold text-slate-900">
                  Hồ Sơ Dược Lý & Hướng Dẫn Sử Dụng Từng Thuốc
                </h4>
                <div className="grid grid-cols-1 gap-3.5">
                  {result.medicationProfiles.map((med, idx) => (
                    <div
                      key={idx}
                      className="rounded-lg border border-slate-200 bg-white p-4 space-y-2.5"
                    >
                      <div className="border-b border-slate-100 pb-2">
                        <h5 className="text-sm font-bold text-slate-900">
                          {med.name}
                        </h5>
                        <p className="text-xs text-slate-500 mt-0.5">
                          <span>Hoạt chất: {med.activeIngredient}</span>
                          <span aria-hidden="true"> · </span>
                          <span>Công dụng: {med.mainUse}</span>
                        </p>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                        <div>
                          <span className="font-semibold text-slate-900 block">
                            Thời điểm uống tốt nhất:
                          </span>
                          <p className="text-slate-700 mt-0.5 leading-relaxed">
                            {med.bestTiming}
                          </p>
                        </div>
                        <div>
                          <span className="font-semibold text-slate-900 block">
                            Thực phẩm / Đồ uống cần tránh:
                          </span>
                          <p className="text-slate-700 mt-0.5 leading-relaxed">
                            {med.foodInteractions}
                          </p>
                        </div>
                      </div>

                      {med.commonSideEffects.length > 0 && (
                        <p className="text-xs text-slate-600 pt-1">
                          <strong className="text-slate-800">
                            Tác dụng phụ cần lưu ý:{' '}
                          </strong>
                          {med.commonSideEffects.join(' · ')}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-xl border border-slate-200 bg-white p-10 text-center space-y-3">
            <Pill className="mx-auto h-8 w-8 text-slate-400" />
            <h3 className="text-base font-bold text-slate-900">
              Kiểm tra tương tác thuốc an toàn
            </h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Thêm các loại thuốc bạn đang sử dụng ở cột bên trái để phân tích tương tác và nhận hướng dẫn chia giờ uống tối ưu.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

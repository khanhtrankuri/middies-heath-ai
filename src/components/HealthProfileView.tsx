import React, { useState } from 'react';
import {
  UserCheck,
  Plus,
  Trash2,
  CheckSquare,
  Square,
  Activity,
  Download,
  Upload,
  RotateCcw,
  AlertTriangle,
  Clock,
} from 'lucide-react';
import {
  MedicationReminder,
  MedicationSlot,
  PatientProfile,
  VitalLog,
} from '../types/health';
import { getTodayDateString } from '../data/defaultHealthData';

interface HealthProfileViewProps {
  profile: PatientProfile;
  onUpdateProfile: (next: PatientProfile) => void;
  onExportBackup: () => void;
  onImportBackup: (file: File) => void;
  onResetDefault: () => void;
}

const SLOTS: MedicationSlot[] = ['Sáng', 'Trưa', 'Chiều', 'Tối'];

export const HealthProfileView: React.FC<HealthProfileViewProps> = ({
  profile,
  onUpdateProfile,
  onExportBackup,
  onImportBackup,
  onResetDefault,
}) => {
  const [newAllergy, setNewAllergy] = useState('');
  const [newCondition, setNewCondition] = useState('');

  // New Medication Form State
  const [medName, setMedName] = useState('');
  const [medDosage, setMedDosage] = useState('1 viên');
  const [medInstructions, setMedInstructions] = useState('Uống sau ăn');
  const [medPurpose, setMedPurpose] = useState('');
  const [medSlots, setMedSlots] = useState<MedicationSlot[]>(['Sáng']);

  // New Vital Log State
  const [sysInput, setSysInput] = useState('122');
  const [diaInput, setDiaInput] = useState('78');
  const [hrInput, setHrInput] = useState('72');
  const [sugarInput, setSugarInput] = useState('5.3');
  const [tempInput, setTempInput] = useState('36.6');
  const [vitalNote, setVitalNote] = useState('');

  const bmiValue =
    profile.heightCm > 0 && profile.weightKg > 0
      ? Number(
          (
            profile.weightKg / Math.pow(profile.heightCm / 100, 2)
          ).toFixed(1)
        )
      : 0;

  const getBmiClassification = (bmi: number) => {
    if (!bmi) return 'Chưa rõ';
    if (bmi < 18.5) return 'Thiếu cân';
    if (bmi < 23) return 'Bình thường (Chuẩn châu Á)';
    if (bmi < 25) return 'Thừa cân nhẹ';
    return 'Béo phì — Cần kiểm soát chuyển hóa';
  };

  const handleToggleSlotTaken = (medId: string, slot: MedicationSlot) => {
    const today = getTodayDateString();
    const updatedMeds = profile.medications.map((m) => {
      if (m.id !== medId) return m;
      const currentTaken =
        m.lastUpdatedDate === today ? m.takenSlotsToday : [];
      const exists = currentTaken.includes(slot);
      const nextTaken = exists
        ? currentTaken.filter((s) => s !== slot)
        : [...currentTaken, slot];
      return {
        ...m,
        takenSlotsToday: nextTaken,
        lastUpdatedDate: today,
      };
    });
    onUpdateProfile({ ...profile, medications: updatedMeds });
  };

  const handleAddMedication = (e: React.FormEvent) => {
    e.preventDefault();
    if (!medName.trim()) return;
    const newMed: MedicationReminder = {
      id: `med-${Date.now()}`,
      name: medName.trim(),
      dosage: medDosage.trim() || '1 viên',
      frequency: `${medSlots.length} lần/ngày`,
      slots: medSlots.length > 0 ? medSlots : ['Sáng'],
      instructions: medInstructions.trim() || 'Uống theo chỉ định',
      purpose: medPurpose.trim() || 'Hỗ trợ điều trị',
      takenSlotsToday: [],
      lastUpdatedDate: getTodayDateString(),
    };
    onUpdateProfile({
      ...profile,
      medications: [...profile.medications, newMed],
    });
    setMedName('');
    setMedPurpose('');
  };

  const handleDeleteMedication = (id: string) => {
    onUpdateProfile({
      ...profile,
      medications: profile.medications.filter((m) => m.id !== id),
    });
  };

  const handleAddVitalLog = (e: React.FormEvent) => {
    e.preventDefault();
    const sys = Number(sysInput);
    const dia = Number(diaInput);
    const hr = Number(hrInput);
    if (!sys || !dia || !hr) return;

    const now = new Date();
    const formattedDate = `${now.toISOString().split('T')[0]} ${now
      .toTimeString()
      .slice(0, 5)}`;

    const newLog: VitalLog = {
      id: `vital-${Date.now()}`,
      recordedAt: formattedDate,
      systolic: sys,
      diastolic: dia,
      heartRate: hr,
      bloodSugar: sugarInput ? Number(sugarInput) : undefined,
      temperatureC: tempInput ? Number(tempInput) : undefined,
      note: vitalNote.trim() || 'Đo định kỳ tại nhà',
    };

    onUpdateProfile({
      ...profile,
      vitalLogs: [newLog, ...profile.vitalLogs],
    });
    setVitalNote('');
  };

  // Calculate today's medication adherence
  const totalScheduledDoses = profile.medications.reduce(
    (acc, m) => acc + m.slots.length,
    0
  );
  const totalTakenDoses = profile.medications.reduce(
    (acc, m) => acc + m.takenSlotsToday.length,
    0
  );

  return (
    <div className="space-y-6">
      {/* Top Section: Daily Medication Reminder Tracker & Add Medication */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-7 rounded-xl border border-slate-200 bg-white p-6 space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Lịch Nhắc Uống Thuốc Hôm Nay ({getTodayDateString()})
              </h2>
              <p className="text-xs text-slate-600 mt-0.5">
                Đánh dấu các cử thuốc đã uống trong ngày để tránh quên liều hoặc uống trùng lặp.
              </p>
            </div>
            <div className="text-right font-mono-tabular">
              <span className="text-xs text-slate-500 block">Tiến độ hôm nay</span>
              <span className="text-sm font-bold text-teal-700">
                {totalTakenDoses} / {totalScheduledDoses} liều đã uống
              </span>
            </div>
          </div>

          {profile.medications.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-xs text-slate-500">
              Chưa có lịch nhắc uống thuốc nào. Bạn có thể thêm thuốc mới ở khung bên phải hoặc lưu tự động từ tính năng Đọc Đơn Thuốc.
            </div>
          ) : (
            <div className="space-y-3">
              {profile.medications.map((med) => (
                <div
                  key={med.id}
                  className="rounded-lg border border-slate-200 bg-slate-50/60 p-4 space-y-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-bold text-slate-900">
                        {med.name}
                      </h3>
                      <p className="text-xs text-slate-600 mt-0.5">
                        <span className="font-mono-tabular font-semibold text-slate-800">
                          Liều: {med.dosage}
                        </span>
                        <span aria-hidden="true"> · </span>
                        <span>{med.instructions}</span>
                        {med.purpose && (
                          <>
                            <span aria-hidden="true"> · </span>
                            <span>{med.purpose}</span>
                          </>
                        )}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDeleteMedication(med.id)}
                      className="rounded p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600 transition-colors shrink-0"
                      title="Xóa thuốc khỏi lịch nhắc"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>

                  {/* Interactive Slot Checkboxes */}
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <span className="text-xs font-medium text-slate-500 mr-1">
                      Cử uống:
                    </span>
                    {med.slots.map((slot) => {
                      const isTaken = med.takenSlotsToday.includes(slot);
                      return (
                        <button
                          key={slot}
                          type="button"
                          onClick={() => handleToggleSlotTaken(med.id, slot)}
                          className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors whitespace-nowrap shrink-0 ${
                            isTaken
                              ? 'border-emerald-300 bg-emerald-50 text-emerald-900'
                              : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'
                          }`}
                        >
                          {isTaken ? (
                            <CheckSquare className="h-3.5 w-3.5 text-emerald-600" />
                          ) : (
                            <Square className="h-3.5 w-3.5 text-slate-400" />
                          )}
                          <span>Buổi {slot}</span>
                          <span className="font-normal opacity-80">
                            {isTaken ? '(Đã uống)' : '(Chưa uống)'}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Add New Medication Reminder Form */}
        <form
          onSubmit={handleAddMedication}
          className="lg:col-span-5 rounded-xl border border-slate-200 bg-white p-6 space-y-4"
        >
          <div className="border-b border-slate-200 pb-3">
            <h3 className="text-sm font-bold text-slate-900">
              Thêm Thuốc Vào Lịch Nhắc Hàng Ngày
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Thuốc thêm tại đây cũng sẽ được AI tự động kiểm tra tương tác khi bạn hỏi bệnh.
            </p>
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <label className="font-semibold text-slate-700 block mb-1">
                Tên thuốc & Hàm lượng *
              </label>
              <input
                type="text"
                required
                value={medName}
                onChange={(e) => setMedName(e.target.value)}
                placeholder="VD: Amlodipine 5mg hoặc Vitamin D3 1000IU"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-teal-600 focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="font-semibold text-slate-700 block mb-1">
                  Liều dùng mỗi lần
                </label>
                <input
                  type="text"
                  value={medDosage}
                  onChange={(e) => setMedDosage(e.target.value)}
                  placeholder="VD: 1 viên"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-teal-600 focus:outline-none"
                />
              </div>
              <div>
                <label className="font-semibold text-slate-700 block mb-1">
                  Thời điểm (Trước/Sau ăn)
                </label>
                <input
                  type="text"
                  value={medInstructions}
                  onChange={(e) => setMedInstructions(e.target.value)}
                  placeholder="VD: Uống sau ăn 30 phút"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-teal-600 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="font-semibold text-slate-700 block mb-1.5">
                Chọn các buổi uống trong ngày:
              </label>
              <div className="flex flex-wrap gap-2">
                {SLOTS.map((slot) => {
                  const active = medSlots.includes(slot);
                  return (
                    <button
                      key={slot}
                      type="button"
                      onClick={() => {
                        setMedSlots((prev) =>
                          prev.includes(slot)
                            ? prev.filter((s) => s !== slot)
                            : [...prev, slot]
                        );
                      }}
                      className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors ${
                        active
                          ? 'border-teal-600 bg-teal-50 text-teal-900'
                          : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      Buổi {slot}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="font-semibold text-slate-700 block mb-1">
                Mục đích điều trị / Ghi chú
              </label>
              <input
                type="text"
                value={medPurpose}
                onChange={(e) => setMedPurpose(e.target.value)}
                placeholder="VD: Kiểm soát huyết áp buổi sáng"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-teal-600 focus:outline-none"
              />
            </div>
          </div>

          <button
            type="submit"
            className="w-full flex items-center justify-center gap-1.5 rounded-lg bg-teal-600 px-4 py-2.5 text-xs font-semibold text-white hover:bg-teal-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            <span>Thêm Vào Lịch Nhắc Uống Thuốc</span>
          </button>
        </form>
      </div>

      {/* Bottom Section: Personal Health Record & Vital Signs Logger */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Patient Demographics, Allergies & Chronic Conditions */}
        <div className="lg:col-span-6 rounded-xl border border-slate-200 bg-white p-6 space-y-5">
          <div className="flex items-center justify-between border-b border-slate-200 pb-4">
            <div className="flex items-center gap-2.5">
              <UserCheck className="h-5 w-5 text-teal-600" />
              <div>
                <h2 className="text-base font-bold text-slate-900">
                  Hồ Sơ Sức Khỏe Cá Nhân & Tiền Sử Y Khoa
                </h2>
                <p className="text-xs text-slate-500">
                  Lưu trữ cục bộ riêng tư trên trình duyệt của bạn
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
            <div className="col-span-2 sm:col-span-1">
              <label className="font-semibold text-slate-700 block mb-1">
                Họ và tên
              </label>
              <input
                type="text"
                value={profile.fullName}
                onChange={(e) =>
                  onUpdateProfile({ ...profile, fullName: e.target.value })
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900"
              />
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">
                Năm sinh
              </label>
              <input
                type="number"
                value={profile.birthYear}
                onChange={(e) =>
                  onUpdateProfile({
                    ...profile,
                    birthYear: Number(e.target.value) || 1990,
                  })
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono-tabular text-slate-900"
              />
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">
                Nhóm máu
              </label>
              <select
                value={profile.bloodType}
                onChange={(e) =>
                  onUpdateProfile({
                    ...profile,
                    bloodType: e.target.value as PatientProfile['bloodType'],
                  })
                }
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono-tabular text-slate-900"
              >
                {['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'Chưa rõ'].map(
                  (bt) => (
                    <option key={bt} value={bt}>
                      {bt}
                    </option>
                  )
                )}
              </select>
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">
                Chiều cao (cm)
              </label>
              <input
                type="number"
                value={profile.heightCm}
                onChange={(e) =>
                  onUpdateProfile({
                    ...profile,
                    heightCm: Number(e.target.value) || 0,
                  })
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono-tabular text-slate-900"
              />
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">
                Cân nặng (kg)
              </label>
              <input
                type="number"
                value={profile.weightKg}
                onChange={(e) =>
                  onUpdateProfile({
                    ...profile,
                    weightKg: Number(e.target.value) || 0,
                  })
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono-tabular text-slate-900"
              />
            </div>
            <div>
              <span className="font-semibold text-slate-700 block mb-1">
                Chỉ số BMI tự động
              </span>
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 font-mono-tabular font-bold text-teal-800">
                {bmiValue} — <span className="font-sans font-normal text-slate-600">{getBmiClassification(bmiValue)}</span>
              </div>
            </div>
          </div>

          {/* Allergies Manager */}
          <div className="space-y-2 pt-2 border-t border-slate-200">
            <label className="text-xs font-bold text-red-700 flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5" />
              <span>Tiền Sử Dị Ứng Thuốc / Thực Phẩm (Quan trọng)</span>
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={newAllergy}
                onChange={(e) => setNewAllergy(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && newAllergy.trim()) {
                    e.preventDefault();
                    onUpdateProfile({
                      ...profile,
                      allergies: [...profile.allergies, newAllergy.trim()],
                    });
                    setNewAllergy('');
                  }
                }}
                placeholder="Thêm dị ứng mới (VD: Kháng sinh Cephalosporin, Phấn hoa)..."
                className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs"
              />
              <button
                type="button"
                onClick={() => {
                  if (!newAllergy.trim()) return;
                  onUpdateProfile({
                    ...profile,
                    allergies: [...profile.allergies, newAllergy.trim()],
                  });
                  setNewAllergy('');
                }}
                className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800 whitespace-nowrap"
              >
                + Thêm
              </button>
            </div>
            <div className="space-y-1.5 pt-1">
              {profile.allergies.map((al, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between rounded-md border border-red-200 bg-red-50/50 px-3 py-1.5 text-xs text-red-950"
                >
                  <span>{al}</span>
                  <button
                    type="button"
                    onClick={() =>
                      onUpdateProfile({
                        ...profile,
                        allergies: profile.allergies.filter((_, idx) => idx !== i),
                      })
                    }
                    className="text-red-600 hover:text-red-800 font-medium"
                  >
                    Gỡ bỏ
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Chronic Conditions Manager */}
          <div className="space-y-2 pt-2 border-t border-slate-200">
            <label className="text-xs font-bold text-slate-900 block">
              Bệnh Lý Nền / Tình Trạng Sức Khỏe Đang Theo Dõi
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={newCondition}
                onChange={(e) => setNewCondition(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && newCondition.trim()) {
                    e.preventDefault();
                    onUpdateProfile({
                      ...profile,
                      chronicConditions: [
                        ...profile.chronicConditions,
                        newCondition.trim(),
                      ],
                    });
                    setNewCondition('');
                  }
                }}
                placeholder="Thêm bệnh lý nền (VD: Tiểu đường tuýp 2, Hen phế quản)..."
                className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs"
              />
              <button
                type="button"
                onClick={() => {
                  if (!newCondition.trim()) return;
                  onUpdateProfile({
                    ...profile,
                    chronicConditions: [
                      ...profile.chronicConditions,
                      newCondition.trim(),
                    ],
                  });
                  setNewCondition('');
                }}
                className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800 whitespace-nowrap"
              >
                + Thêm
              </button>
            </div>
            <div className="space-y-1.5 pt-1">
              {profile.chronicConditions.map((cond, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-800"
                >
                  <span>{cond}</span>
                  <button
                    type="button"
                    onClick={() =>
                      onUpdateProfile({
                        ...profile,
                        chronicConditions: profile.chronicConditions.filter(
                          (_, idx) => idx !== i
                        ),
                      })
                    }
                    className="text-slate-500 hover:text-red-600 font-medium"
                  >
                    Gỡ bỏ
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Local Backup & Restore Controls */}
          <div className="pt-4 border-t border-slate-200 flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={onExportBackup}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-100 transition-colors"
              >
                <Download className="h-3.5 w-3.5 text-teal-600" />
                <span>Xuất Tệp Sao Lưu (.json)</span>
              </button>

              <label className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-100 transition-colors cursor-pointer">
                <Upload className="h-3.5 w-3.5 text-teal-600" />
                <span>Khôi Phục Từ Tệp</span>
                <input
                  type="file"
                  accept="application/json"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) onImportBackup(file);
                    e.target.value = '';
                  }}
                  className="hidden"
                />
              </label>
            </div>

            <button
              type="button"
              onClick={onResetDefault}
              className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-red-600"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Đặt lại dữ liệu mẫu</span>
            </button>
          </div>
        </div>

        {/* Vital Signs Logger & Tabular History */}
        <div className="lg:col-span-6 rounded-xl border border-slate-200 bg-white p-6 space-y-5">
          <div className="flex items-center gap-2.5 border-b border-slate-200 pb-4">
            <Activity className="h-5 w-5 text-teal-600" />
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Nhật Ký Chỉ Số Sinh Tồn (Huyết Áp · Nhịp Tim · Đường Huyết)
              </h2>
              <p className="text-xs text-slate-500">
                Theo dõi định kỳ để phát hiện sớm bất thường tim mạch và chuyển hóa
              </p>
            </div>
          </div>

          <form onSubmit={handleAddVitalLog} className="space-y-3 text-xs">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
              <div>
                <label className="font-semibold text-slate-700 block mb-1">
                  Tâm thu (mmHg)
                </label>
                <input
                  type="number"
                  required
                  value={sysInput}
                  onChange={(e) => setSysInput(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 font-mono-tabular"
                />
              </div>
              <div>
                <label className="font-semibold text-slate-700 block mb-1">
                  Tâm trương
                </label>
                <input
                  type="number"
                  required
                  value={diaInput}
                  onChange={(e) => setDiaInput(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 font-mono-tabular"
                />
              </div>
              <div>
                <label className="font-semibold text-slate-700 block mb-1">
                  Nhịp tim (l/p)
                </label>
                <input
                  type="number"
                  required
                  value={hrInput}
                  onChange={(e) => setHrInput(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 font-mono-tabular"
                />
              </div>
              <div>
                <label className="font-semibold text-slate-700 block mb-1">
                  Đường (mmol/L)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={sugarInput}
                  onChange={(e) => setSugarInput(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 font-mono-tabular"
                />
              </div>
              <div className="col-span-2 sm:col-span-1">
                <label className="font-semibold text-slate-700 block mb-1">
                  Nhiệt độ (°C)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={tempInput}
                  onChange={(e) => setTempInput(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 font-mono-tabular"
                />
              </div>
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                value={vitalNote}
                onChange={(e) => setVitalNote(e.target.value)}
                placeholder="Ghi chú thời điểm đo (VD: Sáng trước ăn, sau tập thể dục)..."
                className="flex-1 rounded-lg border border-slate-300 px-3 py-2"
              />
              <button
                type="submit"
                className="rounded-lg bg-teal-600 px-4 py-2 font-semibold text-white hover:bg-teal-700 transition-colors whitespace-nowrap shrink-0"
              >
                + Ghi chỉ số
              </button>
            </div>
          </form>

          {/* Tabular Vital Logs Table */}
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold text-slate-600">
                  <th className="py-2.5 px-3">Thời gian</th>
                  <th className="py-2.5 px-3 text-right">Huyết áp</th>
                  <th className="py-2.5 px-3 text-right">Nhịp tim</th>
                  <th className="py-2.5 px-3 text-right">Đường huyết</th>
                  <th className="py-2.5 px-3">Đánh giá</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 text-xs">
                {profile.vitalLogs.map((log) => {
                  const isHighBp = log.systolic >= 135 || log.diastolic >= 85;
                  return (
                    <tr key={log.id} className="hover:bg-slate-50">
                      <td className="py-2.5 px-3 font-mono-tabular text-slate-700 whitespace-nowrap">
                        {log.recordedAt}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono-tabular font-bold text-slate-900 whitespace-nowrap">
                        {log.systolic}/{log.diastolic}{' '}
                        <span className="font-normal text-slate-500">mmHg</span>
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono-tabular text-slate-800 whitespace-nowrap">
                        {log.heartRate} <span className="text-slate-500">bpm</span>
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono-tabular text-slate-800 whitespace-nowrap">
                        {log.bloodSugar ? `${log.bloodSugar} mmol/L` : '-'}
                      </td>
                      <td className="py-2.5 px-3 whitespace-nowrap">
                        {isHighBp ? (
                          <span className="font-semibold text-amber-700">
                            ↑ Cần theo dõi HA
                          </span>
                        ) : (
                          <span className="font-semibold text-emerald-700">
                            ✓ Ổn định
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

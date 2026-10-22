import React, { useState } from 'react';
import { AlertTriangle, PhoneCall, ShieldAlert, X, HeartPulse, Brain, Wind, Flame } from 'lucide-react';
import { PatientProfile } from '../types/health';

interface EmergencyGuideModalProps {
  isOpen: boolean;
  onClose: () => void;
  profile: PatientProfile;
}

const EMERGENCY_PROTOCOLS = [
  {
    id: 'stroke',
    title: 'Dấu hiệu Đột quỵ cấp (Quy tắc F.A.S.T)',
    icon: Brain,
    symptoms: [
      'F (Face): Méo miệng, nhân trung lệch khi cười hoặc nhe răng.',
      'A (Arm): Yếu, tê bì hoặc không nâng được một bên tay/chân.',
      'S (Speech): Nói ngọng, nói lắp, khó tìm từ hoặc không hiểu lời nói.',
      'T (Time): Gọi 115 ngay lập tức — từng phút trôi qua làm mất hàng triệu tế bào não.',
    ],
    actions: [
      'Đặt người bệnh nằm nghiêng an toàn, nới lỏng quần áo quanh cổ.',
      'Ghi nhớ chính xác thời điểm khởi phát triệu chứng đầu tiên để báo bác sĩ cấp cứu.',
      'TUYỆT ĐỐI KHÔNG tự ý cho uống thuốc hạ huyết áp, không cạo gió, không chích máu đầu ngón tay và không cho ăn uống gì để tránh sặc vào phổi.',
    ],
  },
  {
    id: 'cardiac',
    title: 'Đau thắt ngực cấp & Nghi ngờ Nhồi máu cơ tim',
    icon: HeartPulse,
    symptoms: [
      'Đau bóp nghẹt, đè nặng sau xương ức kéo dài trên 15 phút.',
      'Cơn đau lan lên cổ, hàm dưới, vai trái hoặc mặt trong cánh tay trái.',
      'Kèm vã mồ hôi lạnh, khó thở, buồn nôn, choáng váng.',
    ],
    actions: [
      'Dừng mọi vận động ngay lập tức; cho người bệnh ngồi tựa lưng nửa nằm nửa ngồi (góc 45 độ).',
      'Gọi cấp cứu 115 ngay hoặc đưa tới bệnh viện có đơn vị can thiệp tim mạch gần nhất.',
      'Nếu người bệnh đã được bác sĩ kê sẵn Nitroglycerin ngậm dưới lưỡi cho cơn đau thắt ngực, sử dụng theo đúng hướng dẫn của bác sĩ.',
    ],
  },
  {
    id: 'anaphylaxis',
    title: 'Phản ứng Dị ứng Nặng / Sốc Phản Vệ',
    icon: Wind,
    symptoms: [
      'Nổi mề đay toàn thân, sưng phù môi, mí mắt, lưỡi hoặc vùng hầu họng sau khi uống thuốc/ăn thức ăn lạ.',
      'Khó thở, thở rít, khàn tiếng, tức ngực.',
      'Đau quặn bụng, nôn ói, tụt huyết áp, tay chân lạnh, lơ mơ.',
    ],
    actions: [
      'Ngừng ngay lập tức tiếp xúc với thuốc hoặc thực phẩm nghi gây dị ứng.',
      'Cho người bệnh nằm ngửa, kê cao hai chân (trừ khi đang nôn hoặc khó thở nhiều thì nằm đầu cao).',
      'Gọi 115 hoặc đưa đến cơ sở y tế gần nhất ngay lập tức để tiêm Adrenalin cấp cứu.',
    ],
  },
  {
    id: 'bleeding_fever',
    title: 'Sốt cao co giật & Xuất huyết tiêu hóa',
    icon: Flame,
    symptoms: [
      'Sốt cao liên tục > 39.5°C không đáp ứng thuốc hạ sốt, kèm lơ mơ, cứng gáy hoặc co giật.',
      'Nôn ra máu tươi hoặc dịch nâu đen; đi ngoài phân đen sệt như bã cà phê kèm chóng mặt.',
    ],
    actions: [
      'Khi đang co giật: Đặt nằm nghiêng sang một bên, kê gối mềm dưới đầu, KHÔNG nhét vật cứng hay ngón tay vào miệng người bệnh.',
      'Lau mát vùng trán, nách, bẹn bằng khăn ấm và đưa tới phòng cấp cứu ngay.',
    ],
  },
];

export const EmergencyGuideModal: React.FC<EmergencyGuideModalProps> = ({
  isOpen,
  onClose,
  profile,
}) => {
  const [selectedId, setSelectedId] = useState<string>('stroke');

  if (!isOpen) return null;

  const activeProtocol =
    EMERGENCY_PROTOCOLS.find((p) => p.id === selectedId) || EMERGENCY_PROTOCOLS[0];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs"
      role="dialog"
      aria-modal="true"
      aria-labelledby="emergency-modal-title"
    >
      <div className="w-full max-w-4xl rounded-xl border border-slate-200 bg-white shadow-xl overflow-hidden">
        {/* Top Emergency Header */}
        <div className="flex items-center justify-between border-b border-red-200 bg-red-50 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-600 text-white shrink-0">
              <ShieldAlert className="h-5 w-5" />
            </div>
            <div>
              <h2 id="emergency-modal-title" className="text-lg font-bold text-red-950">
                Cẩm Nang Nhận Diện Cấp Cứu & Thẻ Y Tế Khẩn Cấp (115)
              </h2>
              <p className="text-xs text-red-800">
                Khi có dấu hiệu đe dọa tính mạng, hãy gọi ngay Trung tâm Cấp cứu 115 hoặc đến cơ sở y tế gần nhất.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-slate-600 hover:bg-red-100 hover:text-slate-900 transition-colors"
            aria-label="Đóng cửa sổ"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12">
          {/* Left column: Patient Medical ID Card for Emergency Responders */}
          <div className="lg:col-span-5 border-b lg:border-b-0 lg:border-r border-slate-200 bg-slate-50 p-6 flex flex-col justify-between">
            <div className="space-y-4">
              <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                <div>
                  <span className="text-xs font-medium text-slate-500">THẺ Y TẾ CÁ NHÂN</span>
                  <h3 className="text-base font-bold text-slate-900">{profile.fullName}</h3>
                </div>
                <div className="text-right">
                  <span className="text-xs text-slate-500">Nhóm máu</span>
                  <p className="font-mono-tabular text-base font-bold text-red-600">
                    {profile.bloodType}
                  </p>
                </div>
              </div>

              <div className="text-xs text-slate-600 space-y-1">
                <p>
                  <span>Năm sinh: </span>
                  <strong className="font-mono-tabular text-slate-900">{profile.birthYear}</strong>
                  <span> · Giới tính: </span>
                  <strong className="text-slate-900">{profile.gender}</strong>
                </p>
                <p>
                  <span>Chỉ số cơ thể: </span>
                  <strong className="font-mono-tabular text-slate-900">
                    {profile.heightCm} cm / {profile.weightKg} kg
                  </strong>
                </p>
              </div>

              <div className="rounded-lg border border-red-200 bg-white p-3.5 space-y-1.5">
                <div className="flex items-center gap-1.5 text-xs font-bold text-red-700">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <span>Tiền sử Dị ứng Cần Tránh Tuyệt Đối</span>
                </div>
                <p className="text-xs text-slate-800 leading-relaxed">
                  {profile.allergies.length > 0
                    ? profile.allergies.join(' · ')
                    : 'Chưa ghi nhận tiền sử dị ứng'}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 bg-white p-3.5 space-y-1.5">
                <span className="text-xs font-semibold text-slate-700 block">
                  Bệnh lý nền & Thuốc đang sử dụng
                </span>
                <p className="text-xs text-slate-600">
                  <strong className="text-slate-800">Bệnh nền: </strong>
                  {profile.chronicConditions.length > 0
                    ? profile.chronicConditions.join(' · ')
                    : 'Không có'}
                </p>
                <p className="text-xs text-slate-600">
                  <strong className="text-slate-800">Thuốc đang dùng: </strong>
                  {profile.medications.length > 0
                    ? profile.medications.map((m) => m.name).join(' · ')
                    : 'Không có'}
                </p>
              </div>
            </div>

            <div className="mt-6 space-y-3 pt-4 border-t border-slate-200">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500">Người liên hệ khẩn cấp:</span>
                <span className="font-semibold text-slate-900">
                  {profile.emergencyContactName || 'Chưa thiết lập'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2.5">
                <a
                  href="tel:115"
                  className="flex items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 text-xs font-semibold text-white hover:bg-red-700 transition-colors whitespace-nowrap"
                >
                  <PhoneCall className="h-4 w-4" />
                  <span>Gọi Cấp Cứu 115</span>
                </a>
                <a
                  href={`tel:${(profile.emergencyContactPhone || '').replace(/\s+/g, '')}`}
                  className="flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-xs font-semibold text-slate-800 hover:bg-slate-100 transition-colors whitespace-nowrap"
                >
                  <PhoneCall className="h-4 w-4 text-teal-600" />
                  <span className="font-mono-tabular truncate">
                    {profile.emergencyContactPhone || 'Người thân'}
                  </span>
                </a>
              </div>
            </div>
          </div>

          {/* Right column: Interactive First-Aid Protocols */}
          <div className="lg:col-span-7 p-6 flex flex-col justify-between">
            <div>
              <div className="flex flex-wrap gap-1.5 rounded-lg bg-slate-100 p-1 mb-5">
                {EMERGENCY_PROTOCOLS.map((protocol) => {
                  const Icon = protocol.icon;
                  const isActive = protocol.id === selectedId;
                  return (
                    <button
                      key={protocol.id}
                      onClick={() => setSelectedId(protocol.id)}
                      className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors whitespace-nowrap shrink-0 ${
                        isActive
                          ? 'bg-white text-slate-900 shadow-xs'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      <Icon className="h-3.5 w-3.5 text-red-600" />
                      <span>{protocol.title.split('(')[0].trim()}</span>
                    </button>
                  );
                })}
              </div>

              <div className="space-y-4">
                <h3 className="text-base font-bold text-slate-900">{activeProtocol.title}</h3>

                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <h4 className="text-xs font-bold text-slate-900 mb-2">
                    1. Dấu hiệu nhận biết khẩn cấp
                  </h4>
                  <ul className="space-y-1.5 text-xs text-slate-700 leading-relaxed">
                    {activeProtocol.symptoms.map((sym, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="font-mono-tabular font-semibold text-red-600 shrink-0">
                          0{idx + 1}.
                        </span>
                        <span>{sym}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-lg border border-teal-200 bg-teal-50/50 p-4">
                  <h4 className="text-xs font-bold text-teal-950 mb-2">
                    2. Hướng dẫn xử trí ban đầu an toàn trong lúc chờ xe cấp cứu
                  </h4>
                  <ul className="space-y-1.5 text-xs text-slate-800 leading-relaxed">
                    {activeProtocol.actions.map((act, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="font-mono-tabular font-semibold text-teal-700 shrink-0">
                          0{idx + 1}.
                        </span>
                        <span>{act}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            <div className="mt-6 flex items-center justify-between border-t border-slate-200 pt-4">
              <p className="text-xs text-slate-500">
                Xuất trình thẻ y tế bên trái cho nhân viên cấp cứu để nắm rõ nhóm máu và dị ứng thuốc.
              </p>
              <button
                onClick={onClose}
                className="rounded-lg bg-slate-900 px-4 py-2 text-xs font-medium text-white hover:bg-slate-800 transition-colors whitespace-nowrap shrink-0"
              >
                Đã hiểu & Đóng
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

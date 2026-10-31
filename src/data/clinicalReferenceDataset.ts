/**
 * Bộ Dữ Liệu Tham Chiếu Lâm Sàng & Phác Đồ Sàng Lọc Y Tế (Local Clinical RAG Dataset)
 * Nguồn chuẩn hóa tham khảo:
 * 1. Hướng dẫn Chẩn đoán & Điều trị — Bộ Y tế Việt Nam (BYT)
 * 2. Dược thư Quốc gia Việt Nam (Vietnamese National Pharmacopoeia)
 * 3. Phân loại bệnh tật Quốc tế ICD-10 & Phác đồ Phân loại Cấp cứu WHO (Emergency Triage)
 * 4. Ngưỡng Cận lâm sàng Huyết học & Sinh hóa máu chuẩn người trưởng thành Việt Nam
 */

export interface ClinicalProtocolEntry {
  id: string;
  icd10Code: string;
  conditionName: string;
  category: string;
  keywords: string[];
  triageDefault: 'NORMAL' | 'MONITOR' | 'SOON' | 'EMERGENCY';
  clinicalCriteria: string;
  redFlags: string[];
  standardGuidance: string;
  contraindications: string[];
}

export const CLINICAL_TRIAGE_DATASET: ClinicalProtocolEntry[] = [
  {
    id: 'byt-gerd-k21',
    icd10Code: 'K21 / K29',
    conditionName: 'Trào ngược dạ dày - thực quản (GERD) & Viêm dạ dày - tá tràng',
    category: 'Tiêu hóa',
    keywords: ['đau thượng vị', 'ợ chua', 'ợ nóng', 'đau dạ dày', 'buồn nôn', 'đầy bụng', 'khó tiêu'],
    triageDefault: 'MONITOR',
    clinicalCriteria:
      'Đau âm ỉ hoặc nóng rát vùng thượng vị, ợ hơi, ợ chua tăng lên sau khi ăn no, đồ chua cay, thức khuya hoặc khi nằm ngay sau ăn.',
    redFlags: [
      'Nôn ra máu tươi hoặc dịch nâu đen như bã cà phê',
      'Đi ngoài phân đen sệt như nhựa đường, mùi khắm',
      'Nuốt nghẹn, nuốt đau tiến triển hoặc sụt cân không rõ nguyên nhân',
      'Đau bụng dữ dội đột ngột kèm co cứng thành bụng (nghi thủng tạng rỗng)',
    ],
    standardGuidance:
      'Dùng nhóm ức chế bơm proton (PPI: Esomeprazole, Omeprazole) trước bữa ăn sáng 30 phút; kết hợp Antacid/Alginate sau ăn 1-2 giờ. Chia nhỏ bữa ăn, kê cao đầu giường 15cm.',
    contraindications: [
      'Chống chỉ định dùng thuốc giảm đau kháng viêm NSAID (Ibuprofen, Aspirin, Meloxicam, Diclofenac) và Corticoid khi đang viêm loét dạ dày.',
    ],
  },
  {
    id: 'byt-uri-j02',
    icd10Code: 'J00 / J02 / J06',
    conditionName: 'Nhiễm khuẩn hô hấp trên cấp tính (Viêm họng cấp / Cảm cúm)',
    category: 'Hô hấp · Tai Mũi Họng',
    keywords: ['sốt', 'đau họng', 'ho khan', 'ho có đờm', 'sổ mũi', 'nghẹt mũi', 'đau mỏi người'],
    triageDefault: 'MONITOR',
    clinicalCriteria:
      'Đa số (70-80%) do virus: sốt nhẹ đến vừa, đau rát họng, ho, chảy nước mũi trong. Viêm họng do liên cầu khuẩn thường sốt cao >38.5°C, hạch góc hàm sưng đau, giả mạc trắng ở amidan.',
    redFlags: [
      'Khó thở, thở nhanh (>24 lần/phút ở người lớn), rút lõm lồng ngực hoặc SpO2 < 95%',
      'Sốt cao >39.5°C liên tục không hạ sau khi dùng Paracetamol đúng liều',
      'Khó nuốt nước bọt, nói giọng ngậm hạt thị, cứng hàm (nghi áp xe quanh amidan)',
      'Lơ mơ, đau đầu dữ dội kèm cứng gáy',
    ],
    standardGuidance:
      'Hạ sốt giảm đau bằng Paracetamol 10-15mg/kg mỗi 4-6 giờ khi sốt >= 38.5°C. Súc họng nước muối sinh lý 0.9%, uống nhiều nước ấm. Không tự ý dùng kháng sinh khi chưa có chỉ định bác sĩ.',
    contraindications: [
      'Nếu bệnh nhân có tiền sử dị ứng Penicillin / Beta-lactam: Tuyệt đối KHÔNG dùng Amoxicillin, Augmentin, Ampicillin và thận trọng tối đa với Cephalosporin.',
    ],
  },
  {
    id: 'byt-htn-i10',
    icd10Code: 'I10',
    conditionName: 'Tăng huyết áp & Cơn tăng huyết áp khẩn cấp/cấp cứu',
    category: 'Tim mạch',
    keywords: ['huyết áp cao', 'tăng huyết áp', 'đau đầu', 'chóng mặt', 'choáng váng', 'đỏ mặt'],
    triageDefault: 'SOON',
    clinicalCriteria:
      'Tiền tăng huyết áp: 130-139/85-89 mmHg. Tăng huyết áp độ 1: 140-159/90-99 mmHg. Cơn tăng huyết áp nặng: >= 180/120 mmHg.',
    redFlags: [
      'Huyết áp >= 180/120 mmHg kèm đau tức ngực, khó thở, nhìn mờ hoặc đau đầu dữ dội',
      'Dấu hiệu đột quỵ F.A.S.T: Méo miệng, yếu tê nửa người, nói ngọng/khó nói',
      'Đau ngực xé lan ra sau lưng (nghi bóc tách động mạch chủ)',
    ],
    standardGuidance:
      'Nghỉ ngơi yên tĩnh 15 phút rồi đo lại huyết áp ở tư thế ngồi chuẩn. Duy trì thuốc hạ áp hàng ngày đúng giờ cố định, ăn nhạt (<5g muối/ngày).',
    contraindications: [
      'Không tự ý nhỏ Nifedipin ngậm dưới lưỡi để hạ áp nhanh vì nguy cơ tụt huyết áp đột ngột gây thiếu máu não/cơ tim.',
      'Tránh thuốc cảm cúm chứa Pseudoephedrine/Phenylephrine và thuốc kháng viêm NSAID vì làm tăng huyết áp.',
    ],
  },
  {
    id: 'byt-allergy-t78',
    icd10Code: 'L50 / T78.2',
    conditionName: 'Mề đay dị ứng cấp & Nguy cơ Phản vệ (Anaphylaxis)',
    category: 'Dị ứng · Miễn dịch',
    keywords: ['nổi mẩn', 'mề đay', 'ngứa', 'dị ứng hải sản', 'dị ứng thuốc', 'sưng môi', 'sưng mắt'],
    triageDefault: 'SOON',
    clinicalCriteria:
      'Sẩn phù hồng ngứa trên da xuất hiện sau tiếp xúc dị nguyên (thức ăn, hải sản, thuốc). Cần phân biệt ngay giữa mề đay đơn thuần (Độ I) và phản vệ Độ II-III.',
    redFlags: [
      'Phù mạch vùng mặt, sưng môi, lưỡi, mí mắt hoặc cảm giác nghẹn cổ họng, khàn tiếng',
      'Khó thở, thở rít, tức ngực, thở khò khè',
      'Đau bụng quặn kèm nôn ói, tiêu chảy ngay sau ăn/uống thuốc',
      'Chóng mặt, choáng váng, tụt huyết áp, vã mồ hôi lạnh (Sốc phản vệ — Gọi 115 ngay)',
    ],
    standardGuidance:
      'Ngưng ngay tác nhân nghi ngờ gây dị ứng. Nếu chỉ nổi mẩn ngứa ngoài da nhẹ không kèm khó thở/sưng mặt: có thể dùng kháng Histamin H1 thế hệ 2 (Fexofenadine, Desloratadine, Cetirizine) và theo dõi sát trong 24 giờ.',
    contraindications: [
      'Tuyệt đối không dùng lại loại thuốc hoặc thực phẩm đã từng gây phản ứng dị ứng.',
    ],
  },
  {
    id: 'byt-acs-i21',
    icd10Code: 'I20 / I21 / I63',
    conditionName: 'Hội chứng Mạch vành cấp & Đột quỵ não cấp',
    category: 'Cấp cứu Nội khoa',
    keywords: ['đau thắt ngực', 'tức ngực', 'khó thở cấp', 'méo miệng', 'yếu nửa người', 'liệt tay chân', 'nói ngọng'],
    triageDefault: 'EMERGENCY',
    clinicalCriteria:
      'Đau ngực kiểu đè nặng, bóp nghẹt sau xương ức >15 phút lan lên hàm/vai trái; hoặc khởi phát đột ngột dấu hiệu thần kinh khu trú (F.A.S.T).',
    redFlags: [
      'Mọi triệu chứng đau thắt ngực cấp, khó thở cấp hoặc dấu hiệu F.A.S.T đều là CẤP CỨU TỐI KHẨN CẤP (Gọi 115 ngay).',
    ],
    standardGuidance:
      'Gọi 115 ngay lập tức. Để bệnh nhân nghỉ ngơi tuyệt đối, nới lỏng quần áo. Không tự ý cho ăn uống hoặc dùng mẹo dân gian (cạo gió, chích máu đầu ngón tay).',
    contraindications: [
      'Không tự ý dùng Aspirin nếu nghi ngờ đột quỵ khi chưa chụp CT loại trừ xuất huyết não.',
    ],
  },
];

export const LAB_REFERENCE_DATASET = [
  { metric: 'Glucose máu lúc đói', normalRange: '3.9 - 5.6 mmol/L', prediabetes: '5.6 - 6.9 mmol/L', diabetes: '>= 7.0 mmol/L' },
  { metric: 'HbA1c', normalRange: '4.0 - 5.6 %', prediabetes: '5.7 - 6.4 %', diabetes: '>= 6.5 %' },
  { metric: 'Cholesterol toàn phần', normalRange: '< 5.2 mmol/L', borderline: '5.2 - 6.2 mmol/L', high: '> 6.2 mmol/L' },
  { metric: 'Triglyceride', normalRange: '< 1.7 mmol/L', borderline: '1.7 - 2.2 mmol/L', high: '>= 2.3 mmol/L' },
  { metric: 'LDL-Cholesterol', normalRange: '< 3.4 mmol/L', optimalForHighRisk: '< 1.8 - 2.6 mmol/L' },
  { metric: 'HDL-Cholesterol', normalRange: '> 1.0 mmol/L (Nam) / > 1.3 mmol/L (Nữ)' },
  { metric: 'AST (GOT) & ALT (GPT)', normalRange: '< 40 U/L', warning: 'Tăng gấp >2-3 lần giới hạn trên cần đánh giá tổn thương tế bào gan' },
  { metric: 'Creatinin huyết thanh', normalRange: '62 - 106 µmol/L (Nam) / 44 - 80 µmol/L (Nữ)' },
  { metric: 'Acid Uric máu', normalRange: '208 - 428 µmol/L (Nam) / 154 - 357 µmol/L (Nữ)' },
];

/**
 * Tìm kiếm các phác đồ lâm sàng liên quan đến câu hỏi của bệnh nhân để bơm vào ngữ cảnh (Local RAG)
 */
export function retrieveClinicalContext(userQuery: string): string {
  const lower = userQuery.toLowerCase();
  const matched = CLINICAL_TRIAGE_DATASET.filter((entry) =>
    entry.keywords.some((kw) => lower.includes(kw.toLowerCase()))
  );

  const selected = matched.length > 0 ? matched : CLINICAL_TRIAGE_DATASET.slice(0, 2);

  return selected
    .map(
      (item) =>
        `- [${item.icd10Code}] ${item.conditionName} (Phân loại mặc định: ${item.triageDefault}):
  + Tiêu chuẩn/Đặc điểm: ${item.clinicalCriteria}
  + Hướng dẫn chuẩn BYT: ${item.standardGuidance}
  + Chống chỉ định/Lưu ý: ${item.contraindications.join(' ')}
  + Dấu hiệu Cờ đỏ (Red Flags): ${item.redFlags.join('; ')}`
    )
    .join('\n');
}

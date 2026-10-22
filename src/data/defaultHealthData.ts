import { ChatSession, DocumentAnalysisResult, PatientProfile } from '../types/health';

export const getTodayDateString = (): string => {
  return new Date().toISOString().split('T')[0];
};

export const DEFAULT_PATIENT_PROFILE: PatientProfile = {
  fullName: 'Nguyễn Minh An',
  birthYear: 1988,
  gender: 'Nam',
  bloodType: 'O+',
  heightCm: 170,
  weightKg: 68,
  allergies: ['Penicillin', 'Dị ứng hải sản có vỏ (Tôm, Cua)'],
  chronicConditions: ['Viêm dạ dày tá tràng nhẹ', 'Tiền tăng huyết áp'],
  emergencyContactName: 'Nguyễn Thị Lan (Vợ)',
  emergencyContactPhone: '0912 345 678',
  medications: [
    {
      id: 'med-1',
      name: 'Esomeprazole 20mg (Nexium)',
      dosage: '1 viên',
      frequency: '1 lần/ngày',
      slots: ['Sáng'],
      instructions: 'Uống trước bữa ăn sáng 30 phút',
      purpose: 'Giảm tiết axit dạ dày, bảo vệ niêm mạc dạ dày',
      takenSlotsToday: ['Sáng'],
      lastUpdatedDate: getTodayDateString(),
    },
    {
      id: 'med-2',
      name: 'Omega-3 Fish Oil 1000mg',
      dosage: '1 viên',
      frequency: '2 lần/ngày',
      slots: ['Sáng', 'Tối'],
      instructions: 'Uống ngay sau bữa ăn',
      purpose: 'Hỗ trợ tim mạch và kiểm soát mỡ máu',
      takenSlotsToday: ['Sáng'],
      lastUpdatedDate: getTodayDateString(),
    },
    {
      id: 'med-3',
      name: 'Magie-B6 Corbière',
      dosage: '1 viên',
      frequency: '1 lần/ngày',
      slots: ['Tối'],
      instructions: 'Uống sau ăn tối với nhiều nước',
      purpose: 'Giảm căng thẳng thần kinh, hỗ trợ giấc ngủ',
      takenSlotsToday: [],
      lastUpdatedDate: getTodayDateString(),
    },
  ],
  vitalLogs: [
    {
      id: 'vital-1',
      recordedAt: '2026-10-21 07:30',
      systolic: 126,
      diastolic: 82,
      heartRate: 74,
      bloodSugar: 5.4,
      temperatureC: 36.6,
      note: 'Đo buổi sáng trước khi ăn, cơ thể khỏe mạnh',
    },
    {
      id: 'vital-2',
      recordedAt: '2026-10-19 20:15',
      systolic: 132,
      diastolic: 85,
      heartRate: 78,
      bloodSugar: 5.8,
      temperatureC: 36.7,
      note: 'Sau ngày làm việc căng thẳng',
    },
    {
      id: 'vital-3',
      recordedAt: '2026-10-16 07:45',
      systolic: 124,
      diastolic: 80,
      heartRate: 71,
      bloodSugar: 5.2,
      temperatureC: 36.5,
      note: 'Đo định kỳ buổi sáng',
    },
  ],
};

export const INITIAL_CHAT_SESSIONS: ChatSession[] = [
  {
    id: 'session-welcome',
    title: 'Đau âm ỉ vùng thượng vị kèm ợ chua',
    createdAt: '2026-10-21T08:00:00.000Z',
    updatedAt: '2026-10-21T08:05:00.000Z',
    lastTriageLevel: 'MONITOR',
    messages: [
      {
        id: 'msg-1',
        role: 'user',
        content:
          'Mấy hôm nay tôi thức khuya làm việc nên bị đau âm ỉ vùng thượng vị, hay ợ chua vào buổi chiều và khi đói. Tôi đang có sẵn thuốc giảm đau Ibuprofen ở nhà thì có nên uống không?',
        timestamp: '08:02',
      },
      {
        id: 'msg-2',
        role: 'assistant',
        content:
          'Chào anh Minh An, dựa trên triệu chứng đau âm ỉ vùng thượng vị kèm ợ chua và tiền sử Viêm dạ dày tá tràng trong hồ sơ của anh, tuyệt đối KHÔNG nên tự ý uống Ibuprofen để giảm đau dạ dày.',
        timestamp: '08:02',
        triageData: {
          triageLevel: 'MONITOR',
          triageTitle: 'Theo dõi tại nhà & Tránh dùng thuốc kháng viêm NSAID',
          summary:
            'Triệu chứng đau âm ỉ thượng vị kèm ợ chua khi đói và thức khuya là biểu hiện điển hình của đợt kích ứng tăng tiết axit dạ dày - trào ngược. Thuốc Ibuprofen thuộc nhóm NSAID sẽ làm tổn thương niêm mạc dạ dày nặng hơn và có nguy cơ gây xuất huyết tiêu hóa.',
          detailedExplanation:
            '1. Vì sao không được dùng Ibuprofen: Ibuprofen ức chế tổng hợp Prostaglandin — chất bảo vệ niêm mạc dạ dày, khiến axit ăn mòn thành dạ dày mạnh hơn.\n2. Xử trí phù hợp: Anh đang có Esomeprazole 20mg trong lịch thuốc buổi sáng, hãy duy trì uống đúng giờ trước ăn sáng 30 phút. Khi đang đau rát thượng vị, có thể dùng thêm thuốc trung hòa axit dạng gói (Antacid như Phosphalugel hoặc Gaviscon) sau ăn 1-2 giờ hoặc lúc đau.\n3. Điều chỉnh sinh hoạt: Chia nhỏ bữa ăn, không để bụng quá đói hoặc ăn quá no, ngưng cà phê/đồ chua cay và ngủ trước 23h00.',
          possibleCauses: [
            'Đợt cấp viêm dạ dày - tá tràng do căng thẳng (Stress) và thức khuya',
            'Trào ngược dạ dày - thực quản (GERD)',
            'Tăng tiết axit dịch vị khi để bụng đói kéo dài',
          ],
          selfCareSteps: [
            'Uống 1 cốc nước ấm từng ngụm nhỏ để làm dịu và rửa trôi axit thực quản',
            'Duy trì uống Esomeprazole 20mg trước bữa sáng 30 phút theo đơn hiện có',
            'Ăn thức ăn mềm, dễ tiêu (cháo, súp, bánh mì mềm); kê cao đầu giường 15cm khi nằm',
            'Tuyệt đối tránh Ibuprofen, Aspirin, Diclofenac, rượu bia và cà phê lúc bụng rỗng',
          ],
          redFlags: [
            'Đau bụng dữ dội đột ngột như dao đâm, bụng cứng như gỗ',
            'Nôn ra máu tươi hoặc dịch màu nâu đen như bã cà phê',
            'Đi ngoài phân đen sệt như nhựa đường, hoa mắt chóng mặt, vã mồ hôi lạnh',
          ],
          personalizedNotes:
            'Hồ sơ của anh ghi nhận tiền sử Viêm dạ dày tá tràng nhẹ và Dị ứng Penicillin. Tuyệt đối tránh nhóm giảm đau kháng viêm không steroid (NSAIDs) như Ibuprofen, Meloxicam, Aspirin. Nếu cần dùng thuốc giảm đau hạ sốt thông thường, Paracetamol an toàn hơn cho dạ dày nhưng chỉ dùng khi thực sự cần.',
          followUpQuestions: [
            'Tôi có thể dùng gói chữ P (Phosphalugel) cách thuốc Esomeprazole bao lâu?',
            'Thực đơn 3 bữa cho người đang đau thượng vị nên ăn những món gì?',
            'Khi nào tôi cần đi nội soi dạ dày kiểm tra lại?',
          ],
        },
      },
    ],
  },
];

export const SAMPLE_DOCUMENTS_PRESETS = [
  {
    id: 'sample-lab-blood',
    label: 'Mẫu Phiếu Xét Nghiệm Sinh Hóa Máu',
    docType: 'LAB_RESULT',
    description: 'Bảng xét nghiệm Đường huyết, HbA1c, Mỡ máu (Cholesterol, Triglyceride) và Men gan.',
    textContext: `PHIẾU KẾT QUẢ XÉT NGHIỆM SINH HÓA MÁU
Họ tên bệnh nhân: Nguyễn Minh An - Năm sinh: 1988 - Giới tính: Nam
Chẩn đoán lâm sàng: Kiểm tra sức khỏe định kỳ / Theo dõi tiền tăng huyết áp
Danh sách chỉ số:
1. Glucose máu lúc đói (Fasting Glucose): 6.1 mmol/L (Khoảng tham chiếu: 3.9 - 5.6 mmol/L)
2. HbA1c: 5.9 % (Khoảng tham chiếu: 4.0 - 5.6 %)
3. Cholesterol toàn phần: 5.8 mmol/L (Khoảng tham chiếu: < 5.2 mmol/L)
4. Triglyceride: 2.4 mmol/L (Khoảng tham chiếu: < 1.7 mmol/L)
5. HDL-Cholesterol: 1.1 mmol/L (Khoảng tham chiếu: > 1.0 mmol/L)
6. LDL-Cholesterol: 3.6 mmol/L (Khoảng tham chiếu: < 3.4 mmol/L)
7. AST (GOT): 28 U/L (Khoảng tham chiếu: < 40 U/L)
8. ALT (GPT): 34 U/L (Khoảng tham chiếu: < 41 U/L)
9. Creatinin huyết thanh: 84 µmol/L (Khoảng tham chiếu: 62 - 106 µmol/L)
10. Acid Uric máu: 435 µmol/L (Khoảng tham chiếu: 208 - 428 µmol/L)`,
  },
  {
    id: 'sample-prescription-resp',
    label: 'Mẫu Đơn Thuốc Viêm Họng - Dạ Dày',
    docType: 'PRESCRIPTION',
    description: 'Đơn thuốc ngoại trú có kháng sinh nhóm Beta-lactam (để kiểm thử cảnh báo dị ứng Penicillin) và thuốc dạ dày.',
    textContext: `ĐƠN THUỐC NGOẠI TRÚ
Họ tên bệnh nhân: Nguyễn Minh An (1988 - Nam)
Chẩn đoán: Viêm họng cấp / Theo dõi trào ngược dạ dày thực quản (GERD)
Chỉ định thuốc:
1. Amoxicillin + Clavulanic Acid (Augmentin 1g) - Số lượng: 14 viên
   Cách dùng: Ngày uống 2 lần, mỗi lần 1 viên (Sáng - Tối) ngay đầu bữa ăn.
2. Paracetamol (Efferalgan 500mg) - Số lượng: 10 viên
   Cách dùng: Uống 1 viên khi sốt > 38.5 độ C hoặc đau họng nhiều, cách nhau ít nhất 4-6 giờ (Sáng - Chiều).
3. Gaviscon Dual Action (Hỗn dịch gói 10ml) - Số lượng: 14 gói
   Cách dùng: Ngày uống 2 lần, mỗi lần 1 gói (Trưa - Tối) sau bữa ăn 1 giờ và trước khi đi ngủ.
4. Desloratadine (Aerius 5mg) - Số lượng: 7 viên
   Cách dùng: Ngày uống 1 lần, mỗi lần 1 viên vào buổi Tối.`,
  },
];

export const INITIAL_DOCUMENT_HISTORY: DocumentAnalysisResult[] = [
  {
    id: 'doc-initial-1',
    analyzedAt: '2026-10-20 14:20',
    detectedType: 'LAB_RESULT',
    title: 'Kết quả Xét nghiệm Sinh hóa Máu & Chuyển hóa Định kỳ',
    overallSummary:
      'Chức năng gan (AST, ALT) và thận (Creatinin) hoàn toàn bình thường. Tuy nhiên, chỉ số đường huyết lúc đói (6.1 mmol/L), HbA1c (5.9%), mỡ máu (Cholesterol 5.8, Triglyceride 2.4) và Acid Uric (435 µmol/L) đều tăng nhẹ ở ngưỡng ranh giới (Tiền đái tháo đường & Rối loạn lipid máu nhẹ).',
    triageStatus: 'ATTENTION',
    metrics: [
      {
        name: 'Glucose lúc đói',
        value: '6.1',
        unit: 'mmol/L',
        referenceRange: '3.9 - 5.6',
        status: 'HIGH',
        explanation: 'Tăng nhẹ trong ngưỡng rối loạn đường huyết lúc đói (5.6 - 6.9 mmol/L). Cần giảm tinh bột tinh chế và đồ ngọt.',
      },
      {
        name: 'HbA1c',
        value: '5.9',
        unit: '%',
        referenceRange: '4.0 - 5.6',
        status: 'HIGH',
        explanation: 'Phản ánh đường huyết trung bình 3 tháng qua ở ngưỡng Tiền đái tháo đường (5.7% - 6.4%). Có thể đảo ngược bằng chế độ ăn và tập luyện.',
      },
      {
        name: 'Triglyceride',
        value: '2.4',
        unit: 'mmol/L',
        referenceRange: '< 1.7',
        status: 'HIGH',
        explanation: 'Mỡ máu trung tính tăng nhẹ. Việc bổ sung Omega-3 kết hợp giảm chất béo bão hòa, rượu bia và tăng vận động sẽ giúp hạ chỉ số này.',
      },
      {
        name: 'Acid Uric máu',
        value: '435',
        unit: 'µmol/L',
        referenceRange: '208 - 428',
        status: 'HIGH',
        explanation: 'Vượt nhẹ ngưỡng trên. Cần uống đủ 2 - 2.5 lít nước/ngày và hạn chế nội tạng động vật, hải sản, bia.',
      },
      {
        name: 'AST (GOT) & ALT (GPT)',
        value: '28 / 34',
        unit: 'U/L',
        referenceRange: '< 40',
        status: 'NORMAL',
        explanation: 'Men gan nằm trong giới hạn an toàn, chưa có dấu hiệu tổn thương tế bào gan.',
      },
      {
        name: 'Creatinin huyết thanh',
        value: '84',
        unit: 'µmol/L',
        referenceRange: '62 - 106',
        status: 'NORMAL',
        explanation: 'Chức năng lọc cầu thận hoạt động tốt.',
      },
    ],
    extractedMedications: [],
    recommendations: [
      'Áp dụng quy tắc đĩa ăn: 50% rau xanh chất xơ, 25% đạm nạc (cá, ức gà, đậu phụ), 25% tinh bột hấp thu chậm (gạo lứt, yến mạch).',
      'Duy trì đi bộ nhanh hoặc tập thể dục nhịp điệu tối thiểu 30 phút/ngày, 5 ngày/tuần để cải thiện độ nhạy Insulin và giảm Triglyceride.',
      'Uống tối thiểu 2 lít nước lọc mỗi ngày để hỗ trợ đào thải Acid Uric qua thận.',
      'Kiểm tra lại bộ xét nghiệm Đường huyết & Mỡ máu sau 3 tháng điều chỉnh lối sống.',
    ],
    questionsForDoctor: [
      'Với mức Triglyceride 2.4 mmol/L và LDL 3.6 mmol/L, tôi đã cần dùng thuốc nhóm Statin chưa hay ưu tiên thay đổi lối sống trong 3 tháng trước?',
      'Mức HbA1c 5.9% của tôi nên theo dõi lại sau bao lâu?',
    ],
  },
];

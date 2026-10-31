import { normalizeVietnamese } from './medicationCatalog';

export interface MeddiesDialogueTurn {
  turn: number;
  role: 'assistant' | 'user';
  content: string;
  slotExtracted?: string;
}

export interface MeddiesDatasetSample {
  id: string;
  conversationId: string;
  targetDisease: string;
  icd10: string;
  clinicalGroup:
    | 'Tiêu hóa'
    | 'Thần kinh'
    | 'Hô hấp'
    | 'Truyền nhiễm & Sốt'
    | 'Tiết niệu'
    | 'Da liễu & Dị ứng'
    | 'Cơ xương khớp'
    | 'Tim mạch & Tiền đình';
  qualityLevel: 'strict' | 'standard';
  turnsCount: number;
  patientPersona: string;
  initialUserPrompt: string;
  extractedSymptoms: string[];
  followUpQuestionsAsked: string[];
  referenceDiseaseInfo: {
    overview: string;
    typicalSymptoms: string[];
    recommendedSpecialty: string;
    recommendedFacility: string;
    whenToSeeDoctor: string;
    redFlags: string[];
  };
  messages: MeddiesDialogueTurn[];
}

export const MEDDIES_DATASET_METADATA = {
  datasetName: 'Meddies/meddies-consultant',
  huggingfaceUrl: 'https://huggingface.co/datasets/Meddies/meddies-consultant',
  subsetConfig: 'vietnamese',
  pinnedRevision: '05428709a7572f6f0d4aa5045e6ba255fa85af51',
  cleaningVersion: 'dialogue-clean-v1',
  systemPromptVersion: 'consult-vi-v1',
  license: 'CC BY-NC 4.0 (Phi thương mại · Nghiên cứu học thuật)',
  totalRawConversations: 58064,
  retainedStandard: 51320,
  retainedStrict: 33237,
  rejectedStandard: 6744,
  uniqueTargetDiseases: 1236,
  medianTurns: '11 – 13 lượt / hội thoại',
  splits: {
    standard: { train: 41067, validation: 5151, test: 5102 },
    strict: { train: 26561, validation: 3353, test: 3323 },
  },
  leakageChecks: [
    {
      metric: 'Nhóm bệnh trùng lặp giữa Train – Val / Train – Test / Val – Test',
      value: '0 / 0 / 0 nhóm bệnh',
      status: 'Đạt tuyệt đối (Chia 80/10/10 theo nhóm target_disease, seed 42)',
    },
    {
      metric: 'Cặp hội thoại gần trùng lặp (MinHash 64 hoán vị, LSH 16 băng, Jaccard ≥ 0.7)',
      value: '0 cặp (Jaccard tối đa = 0.11)',
      status: 'Đã khử trùng lặp hoàn toàn',
    },
    {
      metric: 'Rò rỉ nhãn target_disease vào message input của mô hình',
      value: '0 trường hợp (Kiểm chứng bằng Unit Test)',
      status: 'An toàn chống học vẹt nhãn bệnh',
    },
  ],
  rejectionReasonsStandard: [
    { code: 'unclosed_reasoning', label: 'Thẻ suy luận <think> không đóng hoàn chỉnh', count: 2547 },
    { code: 'medication_dose', label: 'Lời bác sĩ chứa liều thuốc kê đơn cụ thể', count: 2539 },
    { code: 'emergency_not_escalated', label: 'Ca có dấu hiệu cấp cứu nhưng không khuyên đi cấp cứu', count: 830 },
    { code: 'empty_message', label: 'Lượt tin nhắn rỗng sau khi bóc thẻ suy luận', count: 324 },
    { code: 'consecutive_same_role', label: 'Hai lượt liên tiếp cùng một vai (user/assistant)', count: 283 },
    { code: 'certain_diagnosis', label: 'Khẳng định chẩn đoán chắc chắn thay vì định hướng sàng lọc', count: 179 },
    { code: 'too_few_turns', label: 'Hội thoại quá ngắn (< 2 lượt hỏi đáp)', count: 96 },
  ],
  rejectionReasonsStrict: [
    { code: 'role_inversion_user', label: 'Đảo vai: Lời bác sĩ nằm trong lượt user', count: 16067 },
    { code: 'role_inversion_assistant', label: 'Đảo vai: Lời bệnh nhân nằm trong lượt assistant', count: 1111 },
    { code: 'insufficient_history_taking', label: 'Khai thác bệnh sử chưa đủ (< 2 câu hỏi trong 3 lượt đầu)', count: 948 },
    { code: 'leaked_planning_notes', label: 'Lộ ghi chú lập kế hoạch nội bộ (Phase, FIFE, OPQRST)', count: 645 },
    { code: 'no_followup_question', label: 'Lượt đầu không đặt câu hỏi thu thập thêm triệu chứng', count: 611 },
    { code: 'code_mixing', label: 'Trộn từ tiếng Anh trong lời tư vấn tiếng Việt', count: 260 },
  ],
};

export const MEDDIES_BENCHMARK_EXPERIMENTS = {
  hardware: 'NVIDIA GeForce RTX 4060 Laptop (8 GB VRAM, BF16, QLoRA r=16, 17.43M trainable params)',
  baseModel: 'Qwen/Qwen3-1.7B & Qwen/Qwen2.5-7B-Instruct',
  valLossCurve: [
    { step: 'Base (Bước 0)', e1Base: 2.263, e2Standard: 2.263, e3Strict: 2.263 },
    { step: 'Bước 10', e1Base: 2.263, e2Standard: 1.585, e3Strict: 1.586 },
    { step: 'Bước 20', e1Base: 2.263, e2Standard: 1.462, e3Strict: 1.461 },
    { step: 'Bước 30', e1Base: 2.263, e2Standard: 1.407, e3Strict: 1.409 },
    { step: 'Bước 40', e1Base: 2.263, e2Standard: 1.381, e3Strict: 1.388 },
    { step: 'Bước 52 (Cuối)', e1Base: 2.263, e2Standard: 1.376, e3Strict: 1.385 },
  ],
  metricsTable: [
    {
      metric: 'Tỷ lệ lượt có đặt câu hỏi bổ sung thu thập triệu chứng ↑',
      e1Base: '29.8% [25.3; 35.3]',
      e2Standard: '88.1% [84.1; 91.9]',
      e3Strict: '87.1% [83.0; 90.8]',
      p0Planner: '73.9% [66.1; 80.7]',
      highlight: 'Fine-tune tăng +58.3% khả năng chủ động hỏi bệnh so với mô hình gốc',
    },
    {
      metric: 'Tỷ lệ kết luận / nêu tên bệnh quá sớm ở lượt 1–2 ↓',
      e1Base: '44.1% [38.9; 48.8]',
      e2Standard: '8.8% [5.8; 11.8]',
      e3Strict: '10.2% [6.8; 13.9]',
      p0Planner: '0.0%',
      highlight: 'Giảm -35.3% lỗi vội vàng đoán bệnh khi chưa hỏi đủ thông tin',
    },
    {
      metric: 'Hỏi đúng trường thông tin bệnh sử còn thiếu (Missing Slot Hit) ↑',
      e1Base: '5.8% [3.4; 9.1]',
      e2Standard: '20.7% [15.9; 26.1]',
      e3Strict: '20.0% [14.9; 25.9]',
      p0Planner: '46.8% [38.7; 54.1]',
      highlight: 'Kết hợp P0 Planner + LoRA giúp nhắm trúng thông tin lâm sàng còn thiếu',
    },
    {
      metric: 'Độ phủ thông tin cốt lõi (Information Completeness) ↑',
      e1Base: '6.6%',
      e2Standard: '22.1%',
      e3Strict: '19.1%',
      p0Planner: '37.5%',
      highlight: 'Tăng gấp >3.3 lần độ đầy đủ bệnh sử trước khi đưa ra dự đoán bệnh',
    },
    {
      metric: 'Tỷ lệ phản hồi không an toàn (Unsafe Response Rate) ↓',
      e1Base: '0.6%',
      e2Standard: '0.0%',
      e3Strict: '0.3%',
      p0Planner: '0.0%',
      highlight: 'Đạt 0.0% vi phạm khi kết hợp tầng Safety Router & Guardrail',
    },
  ],
  safetySuiteResults: [
    {
      component: 'Deterministic Emergency Router (evaluate_safety.py)',
      dataset: '90 ca hồi quy cấp cứu & phủ định (safety_cases.json)',
      result: 'Recall = 1.00 (100%) · False Positive = 0.00 (0%)',
    },
    {
      component: 'Medical Scope & Prompt-Injection Guardrail',
      dataset: '15 kịch bản kiểm thử ngoài lĩnh vực & bẻ khóa prompt',
      result: 'Đạt 15/15 (100% chặn thành công)',
    },
    {
      component: 'Dialogue State Tracker (evaluate_dst.py)',
      dataset: '25 ca bệnh chuẩn gán nhãn thủ công (Gold DST)',
      result: 'Symptom F1 = 0.976 · Negation F1 = 0.947 · Slot Accuracy = 0.960',
    },
  ],
};

export const MEDDIES_CONVERSATION_SAMPLES: MeddiesDatasetSample[] = [
  {
    id: 'meddies-gi-001',
    conversationId: 'mc_vi_004821',
    targetDisease: 'Trào ngược dạ dày - thực quản (GERD) & Viêm dạ dày cấp',
    icd10: 'K21.0 / K29.1',
    clinicalGroup: 'Tiêu hóa',
    qualityLevel: 'strict',
    turnsCount: 6,
    patientPersona: 'Nam, 34 tuổi, nhân viên văn phòng, thường xuyên ăn tối muộn và uống cà phê sáng.',
    initialUserPrompt:
      'Bác sĩ ơi, mấy hôm nay tôi hay bị đau âm ỉ vùng thượng vị kèm cảm giác nóng rát ngược lên cổ họng và ợ chua, nhất là sau bữa ăn tối hoặc khi nằm xuống.',
    extractedSymptoms: [
      'Đau âm ỉ vùng thượng vị',
      'Nóng rát sau xương ức lan lên họng',
      'Ợ chua nhiều sau ăn tối và khi nằm',
    ],
    followUpQuestionsAsked: [
      'Triệu chứng này đã kéo dài bao lâu và tần suất xuất hiện mấy lần mỗi tuần?',
      'Bạn có kèm theo nuốt nghẹn, nôn ra máu, đi ngoài phân đen hay sụt cân không rõ nguyên nhân không?',
    ],
    referenceDiseaseInfo: {
      overview:
        'Trào ngược dạ dày - thực quản (GERD) và viêm niêm mạc dạ dày xảy ra khi dịch vị axit trào ngược lên thực quản hoặc kích ứng niêm mạc vùng thượng vị, thường liên quan thói quen ăn muộn, nằm ngay sau ăn và căng thẳng.',
      typicalSymptoms: [
        'Nóng rát vùng thượng vị lan lên sau xương ức (ợ nóng)',
        'Ợ hơi, ợ chua, cảm giác vướng nghẹn vùng cổ họng',
        'Đau tăng khi bụng quá đói hoặc ngay sau bữa ăn nhiều dầu mỡ, chua cay',
      ],
      recommendedSpecialty: 'Chuyên khoa Nội Tiêu hóa',
      recommendedFacility: 'Khoa Nội Tiêu hóa — Bệnh viện Đa khoa hoặc Phòng khám Chuyên khoa Nội',
      whenToSeeDoctor:
        'Nên thăm khám chuyên khoa Nội Tiêu hóa nếu triệu chứng kéo dài trên 2 tuần, tái phát nhiều lần trong tuần hoặc không giảm khi đã điều chỉnh chế độ ăn uống.',
      redFlags: [
        'Nôn ra máu tươi hoặc dịch màu nâu đen như bã cà phê',
        'Đi ngoài phân đen sệt như hắc ín',
        'Nuốt nghẹn tăng dần hoặc sụt cân nhanh không rõ nguyên nhân',
      ],
    },
    messages: [
      {
        turn: 1,
        role: 'user',
        content:
          'Bác sĩ ơi, mấy hôm nay tôi hay bị đau âm ỉ vùng thượng vị kèm cảm giác nóng rát ngược lên cổ họng và ợ chua, nhất là sau bữa ăn tối hoặc khi nằm xuống.',
        slotExtracted: 'Triệu chứng: đau thượng vị, nóng rát, ợ chua · Yếu tố: sau ăn tối, khi nằm',
      },
      {
        turn: 2,
        role: 'assistant',
        content:
          'Chào bạn, tôi ghi nhận bạn đang bị đau âm ỉ vùng thượng vị kèm ợ chua và nóng rát lan lên cổ họng, tăng khi nằm sau ăn tối. Để đánh giá kỹ hơn trước khi đưa ra các khả năng liên quan, bạn cho tôi hỏi: Tình trạng này đã diễn ra bao lâu rồi? Ngoài ra bạn có bị nuốt nghẹn, buồn nôn hay đi ngoài phân đen không?',
      },
      {
        turn: 3,
        role: 'user',
        content:
          'Tôi bị khoảng 5 ngày nay rồi do đợt này thức khuya làm việc và hay ăn khuya. Tôi không bị nuốt nghẹn, không nôn và đi ngoài vẫn bình thường.',
        slotExtracted: 'Thời gian: 5 ngày nay · Loại trừ: không nuốt nghẹn, không nôn, không phân đen',
      },
      {
        turn: 4,
        role: 'assistant',
        content:
          'Cảm ơn bạn đã cung cấp thông tin rõ ràng. Với biểu hiện đau âm ỉ thượng vị, ợ chua, nóng rát sau xương ức tăng khi nằm và khởi phát 5 ngày nay sau đợt thức khuya ăn muộn (đồng thời chưa có dấu hiệu cảnh báo nguy hiểm như phân đen hay nuốt nghẹn), tình trạng của bạn có khả năng liên quan cao nhất đến **Trào ngược dạ dày - thực quản (GERD)** kết hợp **Kích ứng viêm niêm mạc dạ dày cấp**.\n\n**Hướng dẫn tham khảo & Khuyến nghị:**\n1. Tránh ăn trong vòng 2–3 giờ trước khi đi ngủ, kê cao đầu giường 15–20 cm, hạn chế cà phê, đồ chua cay và dầu mỡ.\n2. Bạn nên sắp xếp đến khám tại **Chuyên khoa Nội Tiêu hóa** để bác sĩ kiểm tra trực tiếp và cân nhắc xét nghiệm H. pylori hoặc kê thuốc trung hòa/ức chế axit phù hợp.',
      },
    ],
  },
  {
    id: 'meddies-neuro-002',
    conversationId: 'mc_vi_011904',
    targetDisease: 'Đau nửa đầu Migraine / Đau đầu do căng thẳng',
    icd10: 'G43.9 / G44.2',
    clinicalGroup: 'Thần kinh',
    qualityLevel: 'strict',
    turnsCount: 6,
    patientPersona: 'Nữ, 29 tuổi, làm việc máy tính cường độ cao, thiếu ngủ.',
    initialUserPrompt:
      'Hai ngày nay tôi bị đau nhức một bên thái dương kiểu giật theo nhịp mạch đập, nhìn vào màn hình sáng thấy chói mắt và hơi buồn nôn.',
    extractedSymptoms: [
      'Đau một bên thái dương giật theo nhịp mạch',
      'Sợ ánh sáng (nhìn màn hình chói mắt)',
      'Buồn nôn nhẹ đi kèm',
    ],
    followUpQuestionsAsked: [
      'Bạn có bị sốt cao, cứng cổ hay yếu tê tay chân, nói khó không?',
      'Trước đây bạn đã từng có những cơn đau nửa đầu tương tự chưa và mỗi cơn kéo dài bao lâu?',
    ],
    referenceDiseaseInfo: {
      overview:
        'Đau nửa đầu (Migraine) là bệnh lý đau đầu nguyên phát đặc trưng bởi cơn đau một bên đầu, tính chất đập theo nhịp mạch, mức độ vừa đến nặng, thường kèm buồn nôn hoặc nhạy cảm với ánh sáng và tiếng ồn.',
      typicalSymptoms: [
        'Đau khu trú một bên thái dương hoặc hốc mắt theo nhịp mạch đập',
        'Nhạy cảm với ánh sáng mạnh, tiếng ồn',
        'Buồn nôn hoặc mệt mỏi tăng lên khi vận động gắng sức',
      ],
      recommendedSpecialty: 'Chuyên khoa Nội Thần kinh',
      recommendedFacility: 'Khoa Nội Thần kinh — Bệnh viện Đa khoa',
      whenToSeeDoctor:
        'Nên khám chuyên khoa Nội Thần kinh trong 1–2 ngày để được đánh giá loại trừ nguyên nhân thứ phát và tư vấn phác đồ cắt cơn / dự phòng.',
      redFlags: [
        'Đau đầu dữ dội đột ngột như sét đánh (mức độ nặng nhất từ trước tới nay)',
        'Đau đầu kèm sốt cao, cứng gáy hoặc lơ mơ',
        'Méo miệng, nói ngọng, nhìn đôi hoặc yếu tê nửa người',
      ],
    },
    messages: [
      {
        turn: 1,
        role: 'user',
        content:
          'Hai ngày nay tôi bị đau nhức một bên thái dương kiểu giật theo nhịp mạch đập, nhìn vào màn hình sáng thấy chói mắt và hơi buồn nôn.',
        slotExtracted: 'Triệu chứng: đau đầu một bên, giật theo nhịp, sợ ánh sáng, buồn nôn · Thời gian: 2 ngày',
      },
      {
        turn: 2,
        role: 'assistant',
        content:
          'Tôi ghi nhận bạn đau một bên thái dương kiểu mạch đập 2 ngày nay kèm chói mắt và buồn nôn. Để loại trừ các dấu hiệu thần kinh cấp tính, bạn cho tôi biết thêm: Bạn có bị sốt, cứng cổ, nhìn mờ hay tê yếu tay chân không? Trước đây bạn có hay gặp cơn đau giống vậy khi thiếu ngủ không?',
      },
      {
        turn: 3,
        role: 'user',
        content:
          'Tôi không sốt, cổ vẫn cử động bình thường và tay chân không tê yếu. Thỉnh thoảng thức khuya tôi cũng bị đau nửa đầu như vậy khoảng vài tiếng.',
        slotExtracted: 'Loại trừ: không sốt, không cứng cổ, không yếu liệt · Tiền sử: từng tái phát khi thức khuya',
      },
      {
        turn: 4,
        role: 'assistant',
        content:
          'Với đặc điểm đau một bên thái dương theo nhịp mạch, kèm sợ ánh sáng, buồn nôn nhẹ, tái phát khi thiếu ngủ và không có dấu hiệu thần kinh khu trú hay sốt, bệnh lý có khả năng liên quan cao nhất là **Đau nửa đầu (Migraine)**, cần phân biệt với **Đau đầu do căng thẳng (Tension Headache)**.\n\n**Hướng dẫn tham khảo & Khuyến nghị:**\n1. Nghỉ ngơi trong phòng yên tĩnh, giảm ánh sáng, chườm mát vùng thái dương và uống đủ nước.\n2. Bạn nên đến khám **Chuyên khoa Nội Thần kinh** nếu cơn đau kéo dài hoặc xuất hiện dày hơn để bác sĩ hướng dẫn điều trị phù hợp.',
      },
    ],
  },
  {
    id: 'meddies-resp-003',
    conversationId: 'mc_vi_023115',
    targetDisease: 'Viêm họng cấp / Nhiễm siêu vi đường hô hấp trên',
    icd10: 'J02.9 / J06.9',
    clinicalGroup: 'Hô hấp',
    qualityLevel: 'strict',
    turnsCount: 6,
    patientPersona: 'Nam, 41 tuổi, có tiền sử dị ứng kháng sinh nhóm Penicillin.',
    initialUserPrompt:
      'Tôi bị sốt 38.5 độ từ tối qua, kèm đau rát họng khi nuốt và ho khan từng cơn. Tôi có tiền sử dị ứng Penicillin thì cần lưu ý gì?',
    extractedSymptoms: [
      'Sốt 38.5°C khởi phát cấp tính',
      'Đau rát họng khi nuốt',
      'Ho khan từng cơn',
    ],
    followUpQuestionsAsked: [
      'Bạn có bị khó thở, thở rít, đau tức ngực hay khạc đờm đặc màu vàng xanh không?',
      'Quan sát vùng họng có thấy sưng đỏ nhiều hoặc có chấm mủ trắng ở hai bên amidan không?',
    ],
    referenceDiseaseInfo: {
      overview:
        'Viêm họng cấp và nhiễm siêu vi đường hô hấp trên thường khởi phát đột ngột với sốt vừa, đau rát họng, nuốt đau và ho khan. Phần lớn trường hợp do virus và không cần dùng kháng sinh nếu chưa có bằng chứng bội nhiễm vi khuẩn.',
      typicalSymptoms: [
        'Sốt nhẹ đến vừa (38.0°C – 38.8°C), mệt mỏi, đau mỏi cơ',
        'Đau rát họng tăng khi nuốt nước bọt hoặc thức ăn',
        'Ho khan hoặc ho đờm loãng, nghẹt mũi, sổ mũi',
      ],
      recommendedSpecialty: 'Chuyên khoa Tai Mũi Họng hoặc Nội Hô hấp',
      recommendedFacility: 'Phòng khám Tai Mũi Họng hoặc Khoa Khám bệnh — Bệnh viện Đa khoa',
      whenToSeeDoctor:
        'Nên đi khám nếu sốt cao trên 39°C không đáp ứng hạ sốt, đau họng kèm giả mạc trắng ở amidan, hoặc triệu chứng không giảm sau 3–5 ngày.',
      redFlags: [
        'Khó thở, thở nhanh nông hoặc thở rít thanh quản',
        'Không thể nuốt được nước bọt, chảy nước dãi hoặc cứng hàm',
        'Sốt cao liên tục > 39.5°C kèm lơ mơ',
      ],
    },
    messages: [
      {
        turn: 1,
        role: 'user',
        content:
          'Tôi bị sốt 38.5 độ từ tối qua, kèm đau rát họng khi nuốt và ho khan từng cơn. Tôi có tiền sử dị ứng Penicillin thì cần lưu ý gì?',
        slotExtracted: 'Triệu chứng: sốt 38.5°C, đau rát họng, ho khan · Thời gian: từ tối qua · Dị ứng: Penicillin',
      },
      {
        turn: 2,
        role: 'assistant',
        content:
          'Chào bạn, tôi đã ghi nhận bạn sốt 38.5°C từ tối qua kèm đau rát họng, ho khan và đặc biệt lưu ý tiền sử **dị ứng Penicillin** của bạn. Để đánh giá mức độ và định hướng nguyên nhân, bạn cho tôi hỏi: Bạn có bị khó thở, đau tức ngực hay thấy mủ trắng ở vùng amidan không?',
      },
      {
        turn: 3,
        role: 'user',
        content:
          'Tôi không bị khó thở, không tức ngực, nhìn họng chỉ thấy hơi đỏ chứ không có mủ trắng.',
        slotExtracted: 'Loại trừ: không khó thở, không tức ngực, không giả mạc mủ trắng',
      },
      {
        turn: 4,
        role: 'assistant',
        content:
          'Với triệu chứng sốt 38.5°C mới khởi phát từ tối qua, họng đỏ đau rát, ho khan nhưng không khó thở và không có mủ amidan, tình trạng của bạn phù hợp nhất với **Viêm họng cấp nghi do siêu vi (Nhiễm virus đường hô hấp trên)**.\n\n**Lưu ý an toàn quan trọng với tiền sử dị ứng Penicillin:**\n1. Tuyệt đối không tự ý mua kháng sinh uống tại nhà (đặc biệt tránh nhóm Beta-lactam/Penicillin như Amoxicillin, Augmentin).\n2. Bạn có thể súc họng bằng nước muối sinh lý 0.9% ấm, uống nhiều nước ấm và theo dõi nhiệt độ. Nếu sốt kéo dài quá 48–72 giờ, hãy đến khám **Chuyên khoa Tai Mũi Họng** và thông báo rõ tiền sử dị ứng Penicillin cho bác sĩ.',
      },
    ],
  },
  {
    id: 'meddies-fever-004',
    conversationId: 'mc_vi_031409',
    targetDisease: 'Sốt xuất huyết Dengue (Cần xét nghiệm loại trừ) / Sốt siêu vi cấp',
    icd10: 'A97 / B34.9',
    clinicalGroup: 'Truyền nhiễm & Sốt',
    qualityLevel: 'strict',
    turnsCount: 6,
    patientPersona: 'Nữ, 26 tuổi, sống tại khu vực đang có dịch sốt xuất huyết.',
    initialUserPrompt:
      'Tôi bị sốt cao 39.2 độ liên tục 2 ngày nay, đau nhức hai hốc mắt và mỏi nhức khắp cơ bắp, không bị ho hay sổ mũi.',
    extractedSymptoms: [
      'Sốt cao 39.2°C liên tục 2 ngày',
      'Đau nhức sâu hai hốc mắt',
      'Đau mỏi cơ bắp toàn thân, không ho sổ mũi',
    ],
    followUpQuestionsAsked: [
      'Trên da bạn có xuất hiện các chấm đỏ li ti (không mất màu khi căng da), chảy máu chân răng hay chảy máu cam không?',
      'Bạn có bị đau bụng vùng dưới sườn phải hoặc nôn ói nhiều không?',
    ],
    referenceDiseaseInfo: {
      overview:
        'Sốt xuất huyết Dengue là bệnh truyền nhiễm cấp tính do virus Dengue truyền qua muỗi vằn, đặc trưng bởi sốt cao đột ngột 39–40°C liên tục, đau đầu, đau nhức hai hốc mắt, đau mỏi cơ khớp và thường không kèm triệu chứng hô hấp (ho, sổ mũi).',
      typicalSymptoms: [
        'Sốt cao đột ngột, liên tục, khó hạ hoàn toàn',
        'Đau nhức vùng trán và sau hai hốc mắt',
        'Chấm xuất huyết dưới da, chảy máu chân răng (thường rõ từ ngày thứ 3)',
      ],
      recommendedSpecialty: 'Chuyên khoa Truyền nhiễm hoặc Nội Tổng quát',
      recommendedFacility: 'Khoa Khám bệnh / Khoa Truyền nhiễm — Bệnh viện Đa khoa (Cần xét nghiệm máu NS1Ag & Công thức máu)',
      whenToSeeDoctor:
        'Cần đi khám và làm xét nghiệm máu (Công thức máu, tiểu cầu, Dengue NS1) ngay trong ngày khi sốt cao từ ngày thứ 2 kèm đau hốc mắt.',
      redFlags: [
        'Đau bụng dữ dội hoặc đau tức vùng gan (hạ sườn phải)',
        'Nôn ói liên tục, tay chân lạnh ẩm, vật vã hoặc lừ đừ (nguy hiểm nhất vào ngày thứ 3–7 khi bắt đầu hạ sốt)',
        'Chảy máu mũi, chảy máu chân răng nhiều hoặc nôn ra máu',
      ],
    },
    messages: [
      {
        turn: 1,
        role: 'user',
        content:
          'Tôi bị sốt cao 39.2 độ liên tục 2 ngày nay, đau nhức hai hốc mắt và mỏi nhức khắp cơ bắp, không bị ho hay sổ mũi.',
        slotExtracted: 'Triệu chứng: sốt cao 39.2°C, đau hốc mắt, đau cơ · Loại trừ: không ho, không sổ mũi',
      },
      {
        turn: 2,
        role: 'assistant',
        content:
          'Sốt cao 39.2°C liên tục 2 ngày kèm đau nhức hốc mắt, đau mỏi cơ và không có ho/sổ mũi là bệnh cảnh rất cần lưu ý sàng lọc **Sốt xuất huyết Dengue**. Bạn cho tôi hỏi thêm: Bạn có thấy chấm đỏ dưới da, chảy máu chân răng hay đau bụng, buồn nôn không?',
      },
      {
        turn: 3,
        role: 'user',
        content:
          'Sáng nay đánh răng tôi thấy hơi rớm máu chân răng nhẹ, chưa đau bụng nhưng người rất mệt.',
        slotExtracted: 'Dấu hiệu đi kèm: rớm máu chân răng, mệt nhiều',
      },
      {
        turn: 4,
        role: 'assistant',
        content:
          'Với triệu chứng sốt cao 39.2°C ngày thứ 2, đau hốc mắt, đau mỏi cơ kèm dấu hiệu **rớm máu chân răng**, bệnh lý có khả năng liên quan hàng đầu cần loại trừ ngay là **Sốt xuất huyết Dengue**.\n\n**Khuyến nghị y tế quan trọng (Cần đi khám ngay trong ngày):**\n1. Bạn nên đến **Bệnh viện Đa khoa hoặc Khoa Truyền nhiễm** ngay hôm nay để xét nghiệm Công thức máu (kiểm tra số lượng tiểu cầu, Hematocrit) và test nhanh kháng nguyên Dengue NS1.\n2. **Tuyệt đối KHÔNG dùng Ibuprofen hoặc Aspirin** để hạ sốt vì làm tăng nguy cơ xuất huyết nặng; chỉ bù nước điện giải Oresol và trao đổi trực tiếp với bác sĩ.',
      },
    ],
  },
  {
    id: 'meddies-uri-005',
    conversationId: 'mc_vi_042810',
    targetDisease: 'Viêm bàng quang cấp (Nhiễm khuẩn tiết niệu dưới)',
    icd10: 'N30.0 / N39.0',
    clinicalGroup: 'Tiết niệu',
    qualityLevel: 'strict',
    turnsCount: 6,
    patientPersona: 'Nữ, 32 tuổi, nhân viên kế toán, có thói quen uống ít nước.',
    initialUserPrompt:
      'Từ hôm qua tới giờ tôi đi tiểu bị buốt rát ở cuối bãi, cứ 30 phút lại buồn tiểu một lần nhưng lượng nước tiểu rất ít và tức nhẹ vùng bụng dưới.',
    extractedSymptoms: [
      'Tiểu buốt, tiểu rát cuối bãi',
      'Tiểu rắt nhiều lần, lượng ít',
      'Tức nhẹ vùng hạ vị (bụng dưới)',
    ],
    followUpQuestionsAsked: [
      'Bạn có bị sốt cao, ớn lạnh hay đau nhức vùng hông lưng không?',
      'Nước tiểu có màu đục, mùi khai nồng hoặc lẫn máu hồng không?',
    ],
    referenceDiseaseInfo: {
      overview:
        'Viêm bàng quang cấp là tình trạng nhiễm khuẩn đường tiết niệu dưới phổ biến, gây kích thích niêm mạc bàng quang với tam chứng điển hình: tiểu buốt, tiểu rắt và đau tức vùng trên xương mu (hạ vị).',
      typicalSymptoms: [
        'Cảm giác nóng rát, buốt nhói khi đi tiểu',
        'Buồn tiểu liên tục nhưng mỗi lần đi lượng rất ít',
        'Nước tiểu đục hoặc hồng nhạt, tức vùng bụng dưới',
      ],
      recommendedSpecialty: 'Chuyên khoa Thận - Tiết niệu hoặc Nội Tổng quát',
      recommendedFacility: 'Khoa Thận - Tiết niệu — Bệnh viện Đa khoa (Xét nghiệm Tổng phân tích nước tiểu)',
      whenToSeeDoctor:
        'Nên đi khám trong vòng 24–48 giờ để làm tổng phân tích nước tiểu và dùng thuốc theo chỉ định bác sĩ, tránh để nhiễm trùng ngược dòng lên thận.',
      redFlags: [
        'Sốt cao kèm rét run và đau tức vùng hông lưng (dấu hiệu nghi ngờ viêm thận - bể thận cấp)',
        'Tiểu ra máu đỏ tươi hoặc bí tiểu hoàn toàn',
        'Buồn nôn, nôn nhiều không uống được nước',
      ],
    },
    messages: [
      {
        turn: 1,
        role: 'user',
        content:
          'Từ hôm qua tới giờ tôi đi tiểu bị buốt rát ở cuối bãi, cứ 30 phút lại buồn tiểu một lần nhưng lượng nước tiểu rất ít và tức nhẹ vùng bụng dưới.',
        slotExtracted: 'Triệu chứng: tiểu buốt, tiểu rắt, tức bụng dưới · Thời gian: từ hôm qua',
      },
      {
        turn: 2,
        role: 'assistant',
        content:
          'Tôi ghi nhận bạn có triệu chứng tiểu buốt, tiểu rắt liên tục và tức vùng bụng dưới từ hôm qua. Để phân biệt nhiễm khuẩn tiết niệu dưới với tình trạng lan lên thận, bạn cho tôi hỏi: Bạn có bị sốt, ớn lạnh hay đau vùng hông lưng không? Nước tiểu có đục hoặc có máu không?',
      },
      {
        turn: 3,
        role: 'user',
        content:
          'Tôi không bị sốt và không đau lưng, nhưng nước tiểu nhìn hơi đục hơn bình thường.',
        slotExtracted: 'Tính chất: nước tiểu hơi đục · Loại trừ: không sốt, không đau hông lưng',
      },
      {
        turn: 4,
        role: 'assistant',
        content:
          'Với triệu chứng tiểu buốt, tiểu rắt, tức hạ vị, nước tiểu đục và chưa có sốt hay đau hông lưng, tình trạng của bạn có khả năng liên quan cao nhất đến **Viêm bàng quang cấp (Nhiễm khuẩn đường tiết niệu dưới)**.\n\n**Hướng dẫn tham khảo & Khuyến nghị:**\n1. Bạn nên đến khám **Chuyên khoa Thận - Tiết niệu** trong 1–2 ngày để xét nghiệm Tổng phân tích nước tiểu trước khi dùng kháng sinh.\n2. Uống tăng lượng nước lọc (2–2.5 lít/ngày), không nhịn tiểu. Đi khám ngay lập tức nếu xuất hiện sốt hoặc đau hông lưng.',
      },
    ],
  },
  {
    id: 'meddies-derm-006',
    conversationId: 'mc_vi_050218',
    targetDisease: 'Mày đay dị ứng cấp tính (Nghi do thực phẩm)',
    icd10: 'L50.0',
    clinicalGroup: 'Da liễu & Dị ứng',
    qualityLevel: 'strict',
    turnsCount: 6,
    patientPersona: 'Nam, 38 tuổi, có cơ địa dị ứng hải sản có vỏ (tôm, cua).',
    initialUserPrompt:
      'Khoảng 1 tiếng sau khi ăn súp ở tiệc tối, tôi thấy nổi các mảng sẩn đỏ ngứa râm ran ở hai cánh tay và cổ.',
    extractedSymptoms: [
      'Mảng sẩn phù đỏ ngứa ở cánh tay và cổ',
      'Khởi phát cấp 1 giờ sau ăn tiệc',
    ],
    followUpQuestionsAsked: [
      'Bạn có bị sưng môi, sưng mí mắt, khàn tiếng, nghẹn họng, khó thở hay đau quặn bụng không?',
      'Trong bữa tiệc bạn có ăn tôm, cua, hải sản hoặc dùng loại thuốc nào không?',
    ],
    referenceDiseaseInfo: {
      overview:
        'Mày đay cấp tính là phản ứng quá mẫn của da khi cơ thể tiếp xúc với dị nguyên (thức ăn như hải sản, thuốc, nọc côn trùng), gây giải phóng Histamin làm nổi các sẩn phù hồng đỏ và ngứa nhiều.',
      typicalSymptoms: [
        'Sẩn phù gồ trên mặt da, có bờ rõ, ngứa nhiều',
        'Xuất hiện nhanh trong vòng vài phút đến vài giờ sau tiếp xúc dị nguyên',
      ],
      recommendedSpecialty: 'Chuyên khoa Dị ứng - Miễn dịch lâm sàng hoặc Da liễu',
      recommendedFacility: 'Phòng khám Da liễu / Dị ứng (Hoặc Khoa Cấp cứu nếu kèm dấu hiệu toàn thân)',
      whenToSeeDoctor:
        'Khám sớm nếu ban ngứa lan rộng toàn thân. Cần gọi Cấp cứu 115 hoặc đến cơ sở y tế gần nhất NGAY LẬP TỨC nếu có bất kỳ dấu hiệu phản vệ Độ II trở lên.',
      redFlags: [
        'Sưng phù môi, lưỡi, mí mắt hoặc cảm giác nghẹn tắc cổ họng, khàn giọng',
        'Khó thở, thở khò khè, tức ngực',
        'Đau quặn bụng, nôn ói, hoa mắt chóng mặt (tụt huyết áp)',
      ],
    },
    messages: [
      {
        turn: 1,
        role: 'user',
        content:
          'Khoảng 1 tiếng sau khi ăn súp ở tiệc tối, tôi thấy nổi các mảng sẩn đỏ ngứa râm ran ở hai cánh tay và cổ.',
        slotExtracted: 'Triệu chứng: sẩn đỏ ngứa cánh tay, cổ · Thời gian: 1 giờ sau ăn tiệc',
      },
      {
        turn: 2,
        role: 'assistant',
        content:
          'Nổi sẩn đỏ ngứa ở tay và cổ sau ăn 1 tiếng gợi ý phản ứng dị ứng cấp. Trước tiên, để đảm bảo an toàn loại trừ **Phản vệ tiến triển**, bạn cho tôi biết ngay: Bạn có thấy sưng môi/mắt, nghẹn họng, khó thở, choáng váng hay đau quặn bụng không?',
      },
      {
        turn: 3,
        role: 'user',
        content:
          'May quá tôi không bị khó thở, không sưng môi và không đau bụng, chỉ ngứa ở da tay và cổ thôi. Hỏi lại nhà hàng thì món súp có nước dùng nấu từ vỏ tôm.',
        slotExtracted: 'Dị nguyên: nước dùng vỏ tôm · Loại trừ: không khó thở, không phù môi, không đau bụng',
      },
      {
        turn: 4,
        role: 'assistant',
        content:
          'Hiện tại bạn không có dấu hiệu hô hấp hay tuần hoàn nên phù hợp với **Mày đay dị ứng cấp tính mức độ nhẹ (Độ I)** do tiếp xúc dị nguyên hải sản (vỏ tôm).\n\n**Hướng dẫn xử trí & Theo dõi sát:**\n1. Ngưng hoàn toàn thức ăn nghi ngờ, mặc quần áo thoáng mát, chườm mát vùng da ngứa (tránh gãi trầy xước).\n2. Theo dõi sát trong 24 giờ: Nếu xuất hiện **sưng môi/mắt, khàn tiếng, khó thở hoặc đau bụng**, cần đến ngay **Khoa Cấp cứu cơ sở y tế gần nhất**.',
      },
    ],
  },
];

export function retrieveSimilarMeddiesDialogues(
  query: string,
  topK = 2
): MeddiesDatasetSample[] {
  const normQuery = normalizeVietnamese(query);
  if (!normQuery) return MEDDIES_CONVERSATION_SAMPLES.slice(0, topK);

  const scored = MEDDIES_CONVERSATION_SAMPLES.map((sample) => {
    const searchable = normalizeVietnamese(
      [
        sample.targetDisease,
        sample.clinicalGroup,
        sample.initialUserPrompt,
        ...sample.extractedSymptoms,
        ...sample.referenceDiseaseInfo.typicalSymptoms,
      ].join(' ')
    );

    const queryTokens = normQuery
      .split(/\s+/)
      .filter((tok) => tok.length >= 3);

    let score = 0;
    for (const tok of queryTokens) {
      if (searchable.includes(tok)) score += 2;
    }

    if (
      (normQuery.includes('thuong vi') ||
        normQuery.includes('da day') ||
        normQuery.includes('o chua') ||
        normQuery.includes('day hoi')) &&
      sample.clinicalGroup === 'Tiêu hóa'
    ) {
      score += 10;
    }
    if (
      (normQuery.includes('dau dau') ||
        normQuery.includes('thai duong') ||
        normQuery.includes('chong mat')) &&
      sample.clinicalGroup === 'Thần kinh'
    ) {
      score += 10;
    }
    if (
      (normQuery.includes('dau hong') ||
        normQuery.includes('ho khan') ||
        normQuery.includes('so mui')) &&
      sample.clinicalGroup === 'Hô hấp'
    ) {
      score += 10;
    }
    if (
      (normQuery.includes('sot cao') ||
        normQuery.includes('hoc mat') ||
        normQuery.includes('sot xuat huyet')) &&
      sample.clinicalGroup === 'Truyền nhiễm & Sốt'
    ) {
      score += 10;
    }
    if (
      (normQuery.includes('tieu buot') ||
        normQuery.includes('tieu rat') ||
        normQuery.includes('bung duoi')) &&
      sample.clinicalGroup === 'Tiết niệu'
    ) {
      score += 10;
    }
    if (
      (normQuery.includes('man do') ||
        normQuery.includes('me day') ||
        normQuery.includes('hai san') ||
        normQuery.includes('ngua')) &&
      sample.clinicalGroup === 'Da liễu & Dị ứng'
    ) {
      score += 10;
    }

    return { sample, score };
  });

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, topK).map((s) => s.sample);
}

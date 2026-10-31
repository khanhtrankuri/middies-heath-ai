import { normalizeVietnamese } from '../data/medicationCatalog';
import { localEmergencyKind } from '../../qwen-rag-stack/app/consultation.ts';
import {
  MeddiesDatasetSample,
  retrieveSimilarMeddiesDialogues,
} from '../data/meddiesDatasetSamples';

export interface DialogueSlotValue {
  slot: string;
  label: string;
  value: string;
}

export interface CandidateHypothesis {
  name: string;
  icd10: string;
  matchScore: number;
  supportingEvidence: string[];
  missingEvidence: string[];
  explanation: string;
  referenceInfo: string;
  recommendedFacility: string;
  careLevel: 'routine' | 'soon' | 'urgent';
}

export interface PlannedQuestion {
  slot: string;
  slotLabel: string;
  questionText: string;
  reason: string;
  quickReplies: string[];
}

export interface DialogueStateAnalysis {
  action: 'ASK_MORE' | 'FINALIZE' | 'EMERGENCY' | 'OUT_OF_SCOPE';
  stageNumber: 1 | 2 | 3;
  stageLabel: string;
  profileName: string;
  profileLabel: string;
  collectedSlots: DialogueSlotValue[];
  missingSlots: string[];
  negatedFindings: string[];
  emergencyFlags: string[];
  outOfScopeReason?: string;
  plannedQuestion?: PlannedQuestion;
  candidateHypotheses: CandidateHypothesis[];
  matchedMeddiesSamples: MeddiesDatasetSample[];
}

const EMERGENCY_PATTERNS: { key: string; label: string; patterns: string[] }[] = [
  {
    key: 'stroke_fast',
    label: 'Dấu hiệu nghi ngờ Đột quỵ cấp (Méo miệng / Nói ngọng / Yếu liệt nửa người)',
    patterns: [
      'meo mieng',
      'lech mat',
      'noi ngong',
      'noi kho',
      'yeu tay',
      'yeu chan',
      'liet nua nguoi',
      'te nua nguoi',
    ],
  },
  {
    key: 'chest_pain_dyspnea',
    label: 'Đau thắt ngực cấp / Khó thở cấp tính',
    patterns: [
      'dau nguc trai',
      'dau that nguc',
      'ep nguc',
      'bop nghet nguc',
      'kho tho qua',
      'kho tho cap',
      'tho rit',
      'tim tai',
      'moi tim',
    ],
  },
  {
    key: 'gi_bleeding',
    label: 'Dấu hiệu Xuất huyết tiêu hóa (Nôn ra máu / Đi ngoài phân đen)',
    patterns: [
      'non ra mau',
      'oi ra mau',
      'phan den',
      'di ngoai ra mau tuoi',
      'ho ra mau',
    ],
  },
  {
    key: 'neuro_seizure_syncope',
    label: 'Co giật / Ngất xỉu / Rối loạn ý thức (Lơ mơ)',
    patterns: [
      'co giat',
      'ngat xiu',
      'bat tinh',
      'lo mo',
      'hon me',
      'cung gay',
      'cung co kem sot',
    ],
  },
  {
    key: 'anaphylaxis',
    label: 'Dấu hiệu nghi ngờ Phản vệ nặng (Sưng phù môi mắt / Nghẹn họng / Tụt huyết áp)',
    patterns: [
      'soc phan ve',
      'sung moi',
      'sung luoi',
      'phu ne hong',
      'nghen co hong',
      'tut huyet ap',
    ],
  },
  {
    key: 'self_harm',
    label: 'Khủng hoảng tâm lý khẩn cấp / Ý định tự hại',
    patterns: [
      'muon tu tu',
      'y dinh tu hai',
      'khong muon song',
      'ket thuc cuoc doi',
      'uong thuoc tu tu',
    ],
  },
];

const OUT_OF_SCOPE_PATTERNS: { reason: string; patterns: string[] }[] = [
  {
    reason: 'Yêu cầu can thiệp câu lệnh hệ thống (Prompt Injection)',
    patterns: [
      'bo qua huong dan truoc',
      'ignore previous instructions',
      'in nguyen system prompt',
      'reveal system prompt',
      'system prompt cua ban la gi',
    ],
  },
  {
    reason: 'Chủ đề ngoài phạm vi Y tế & Chăm sóc sức khỏe',
    patterns: [
      'viet code',
      'lap trinh python',
      'lap trinh javascript',
      'vo dich world cup',
      'bong da ngoai hang anh',
      'gia bitcoin',
      'dau tu chung khoan',
      'giai phuong trinh bac',
      'viet bai tho tinh',
      'viet doan van nghi luan xa hoi',
    ],
  },
];

const SYMPTOM_LEXICON: {
  key: string;
  label: string;
  profile: string;
  patterns: string[];
}[] = [
  {
    key: 'dau_thuong_vi',
    label: 'Đau vùng thượng vị / dạ dày',
    profile: 'abdominal',
    patterns: ['thuong vi', 'dau da day', 'dau bao tu', 'nong rat thuong vi', 'nong rat vung nguc'],
  },
  {
    key: 'o_chua',
    label: 'Ợ chua / Ợ nóng trào ngược',
    profile: 'abdominal',
    patterns: ['o chua', 'o nong', 'trao nguoc', 'day hoi', 'day bung'],
  },
  {
    key: 'dau_bung',
    label: 'Đau bụng',
    profile: 'abdominal',
    patterns: ['dau bung', 'quan bung', 'dau quanh ron', 'ho chau phai', 'ha suon phai'],
  },
  {
    key: 'tieu_chay',
    label: 'Tiêu chảy / Rối loạn tiêu hóa',
    profile: 'abdominal',
    patterns: ['tieu chay', 'di ngoai nhieu lan', 'phan long'],
  },
  {
    key: 'buon_non',
    label: 'Buồn nôn / Nôn ói',
    profile: 'abdominal',
    patterns: ['buon non', 'non oi', 'bi non'],
  },
  {
    key: 'sot',
    label: 'Sốt',
    profile: 'fever',
    patterns: ['bi sot', 'sot cao', 'sot 38', 'sot 39', 'nong sot', 'sot nhe'],
  },
  {
    key: 'dau_hoc_mat',
    label: 'Đau nhức hốc mắt / Chảy máu chân răng',
    profile: 'fever',
    patterns: ['hoc mat', 'dau nhuc mat', 'chay mau chan rang', 'rom mau chan rang', 'cham xuat huyet'],
  },
  {
    key: 'dau_hong',
    label: 'Đau rát họng',
    profile: 'respiratory',
    patterns: ['dau hong', 'dau rat hong', 'viem hong', 'nuot dau'],
  },
  {
    key: 'ho',
    label: 'Ho',
    profile: 'respiratory',
    patterns: ['ho khan', 'ho co dom', 'bi ho', 'ho nhieu', 'ho tung con'],
  },
  {
    key: 'so_mui',
    label: 'Sổ mũi / Nghẹt mũi',
    profile: 'respiratory',
    patterns: ['so mui', 'nghet mui', 'chay nuoc mui', 'hat hoi'],
  },
  {
    key: 'dau_dau',
    label: 'Đau đầu',
    profile: 'headache',
    patterns: ['dau dau', 'nhuc dau', 'dau nua dau', 'dau vung tran', 'thai duong'],
  },
  {
    key: 'chong_mat',
    label: 'Chóng mặt / Choáng váng',
    profile: 'headache',
    patterns: ['chong mat', 'choang vang', 'choang nhe', 'hoa mat', 'quay cuong'],
  },
  {
    key: 'so_anh_sang',
    label: 'Sợ ánh sáng / Chói mắt',
    profile: 'headache',
    patterns: ['so anh sang', 'choi mat', 'nhin man hinh sang'],
  },
  {
    key: 'noi_man_ngua',
    label: 'Nổi mẩn đỏ / Mề đay ngứa da',
    profile: 'allergy',
    patterns: ['noi man', 'man do', 'me day', 'ngua da', 'san do', 'di ung'],
  },
  {
    key: 'tieu_buot',
    label: 'Tiểu buốt / Tiểu rắt',
    profile: 'urinary',
    patterns: ['tieu buot', 'tieu rat', 'buon tieu', 'tuc bung duoi', 'nuoc tieu duc'],
  },
  {
    key: 'dau_khop',
    label: 'Đau nhức cơ xương khớp / Đau lưng',
    profile: 'musculoskeletal',
    patterns: ['dau khop', 'dau lung', 'dau goi', 'nhuc moi co', 'moi nhuc khap co', 'lan xuong chan'],
  },
];

const PROFILE_METADATA: Record<
  string,
  {
    label: string;
    coreSlots: {
      key: string;
      label: string;
      question: string;
      reason: string;
      quickReplies: string[];
    }[];
  }
> = {
  abdominal: {
    label: 'Tiêu hóa · Dạ dày - Ruột',
    coreSlots: [
      {
        key: 'duration',
        label: 'Thời gian khởi phát',
        question: 'Triệu chứng đau bụng / thượng vị này đã kéo dài bao lâu rồi?',
        reason: 'Phân biệt đợt cấp tính mới khởi phát hay tình trạng mãn tính tái phát.',
        quickReplies: [
          'Mới bị từ tối qua (dưới 24 giờ)',
          'Khoảng 3–5 ngày nay',
          'Đã kéo dài trên 2 tuần và hay tái phát',
        ],
      },
      {
        key: 'location',
        label: 'Vị trí khu trú',
        question: 'Bạn đau rõ nhất ở vị trí nào: vùng thượng vị (trên rốn), quanh rốn hay hố chậu phải?',
        reason: 'Định khu cơ quan tiêu hóa liên quan (dạ dày - tá tràng, ruột non hay ruột thừa).',
        quickReplies: [
          'Đau vùng thượng vị (trên rốn) lan lên ngực',
          'Đau âm ỉ quanh rốn kèm đầy hơi',
          'Đau vùng bụng dưới bên phải tăng dần',
        ],
      },
      {
        key: 'triggers',
        label: 'Liên quan bữa ăn / Thức khuya',
        question: 'Cơn đau hoặc ợ chua tăng lên khi bụng đói, ngay sau khi ăn no hay khi nằm xuống?',
        reason: 'Đánh giá đặc điểm tiết axit dịch vị và cơ chế trào ngược thực quản.',
        quickReplies: [
          'Tăng lên sau bữa ăn tối và khi nằm xuống',
          'Đau nhiều hơn khi bụng đói hoặc uống cà phê',
          'Không kèm nôn ra máu hay phân đen',
        ],
      },
      {
        key: 'red_flag_screen',
        label: 'Sàng lọc dấu hiệu nguy hiểm tiêu hóa',
        question: 'Bạn có kèm theo nôn ói, đi ngoài phân đen, sốt hay sụt cân không?',
        reason: 'Loại trừ sớm biến chứng xuất huyết tiêu hóa hoặc nhiễm trùng đường ruột.',
        quickReplies: [
          'Tôi không nôn, không sốt và đi ngoài bình thường',
          'Có buồn nôn nhẹ nhưng không sốt',
          'Có kèm đi ngoài phân lỏng 2–3 lần',
        ],
      },
    ],
  },
  respiratory: {
    label: 'Hô hấp · Tai Mũi Họng',
    coreSlots: [
      {
        key: 'duration',
        label: 'Thời gian diễn biến',
        question: 'Tình trạng ho / đau rát họng đã bắt đầu từ mấy ngày nay?',
        reason: 'Đánh giá giai đoạn nhiễm siêu vi hay nguy cơ bội nhiễm vi khuẩn.',
        quickReplies: [
          'Mới bị từ tối hôm qua',
          'Khoảng 2–3 ngày nay',
          'Đã kéo dài hơn 1 tuần chưa đỡ',
        ],
      },
      {
        key: 'severity',
        label: 'Thân nhiệt / Mức độ sốt',
        question: 'Bạn đã cặp nhiệt độ chưa và mức sốt cao nhất là bao nhiêu độ C?',
        reason: 'Quyết định ngưỡng cần dùng thuốc hạ sốt và theo dõi đáp ứng.',
        quickReplies: [
          'Sốt nhẹ khoảng 38.0°C – 38.5°C',
          'Sốt cao 38.8°C – 39.2°C',
          'Không bị sốt, chỉ đau rát họng và ho',
        ],
      },
      {
        key: 'character',
        label: 'Tính chất ho & dấu hiệu hô hấp',
        question: 'Bạn ho khan hay ho có đờm, có kèm khó thở hay mủ trắng ở amidan không?',
        reason: 'Phân biệt viêm họng siêu vi với viêm amidan mủ hoặc viêm phế quản.',
        quickReplies: [
          'Ho khan, họng đỏ nhẹ, không khó thở',
          'Ho có đờm đặc, nuốt đau nhiều',
          'Không khó thở và không tức ngực',
        ],
      },
    ],
  },
  fever: {
    label: 'Truyền nhiễm · Sốt cấp tính',
    coreSlots: [
      {
        key: 'severity',
        label: 'Nhiệt độ đo được',
        question: 'Nhiệt độ cơ thể cao nhất bạn đo được là bao nhiêu độ C và có đáp ứng thuốc hạ sốt không?',
        reason: 'Xác định mức độ sốt và hiệu quả của thuốc hạ sốt hiện tại.',
        quickReplies: [
          'Sốt cao 39.0°C – 39.5°C liên tục, khó hạ',
          'Sốt 38.5°C, uống Paracetamol có giảm nhẹ',
          'Sốt từng cơn kèm ớn lạnh',
        ],
      },
      {
        key: 'duration',
        label: 'Số ngày sốt',
        question: 'Bạn bắt đầu sốt từ mấy ngày trước?',
        reason: 'Sốt trên 48 giờ đặc biệt cần xét nghiệm máu loại trừ Sốt xuất huyết Dengue.',
        quickReplies: [
          'Mới sốt ngày đầu tiên (dưới 24 giờ)',
          'Đã sốt sang ngày thứ 2–3',
          'Sốt kéo dài trên 3 ngày',
        ],
      },
      {
        key: 'associated',
        label: 'Sàng lọc dấu hiệu xuất huyết & ổ nhiễm',
        question: 'Ngoài sốt, bạn có đau nhức hốc mắt, chảy máu chân răng, chấm đỏ dưới da hay đau bụng không?',
        reason: 'Sàng lọc tiêu chuẩn lâm sàng của Sốt xuất huyết Dengue.',
        quickReplies: [
          'Có đau nhức hai hốc mắt và mỏi cơ, không ho',
          'Thấy hơi rớm máu chân răng khi đánh răng',
          'Không có chấm xuất huyết và không đau bụng',
        ],
      },
    ],
  },
  headache: {
    label: 'Thần kinh · Huyết áp · Đau đầu',
    coreSlots: [
      {
        key: 'location',
        label: 'Vị trí & Tính chất đau đầu',
        question: 'Bạn đau âm ỉ hai bên trán - thái dương hay đau nhói giật một bên đầu?',
        reason: 'Phân biệt Đau đầu căng thẳng (Tension Headache) với Đau nửa đầu (Migraine).',
        quickReplies: [
          'Đau âm ỉ hai bên trán và thái dương',
          'Đau giật theo nhịp mạch ở một bên thái dương',
          'Đau vùng sau gáy kèm choáng nhẹ khi đứng dậy',
        ],
      },
      {
        key: 'duration',
        label: 'Thời gian & Khởi phát',
        question: 'Cơn đau đầu xuất hiện từ từ hay đột ngột và đã kéo dài mấy ngày?',
        reason: 'Đánh giá tiến triển cơn đau và loại trừ đau đầu sét đánh cấp cứu.',
        quickReplies: [
          'Đau âm ỉ khoảng 2 ngày nay do thiếu ngủ',
          'Đau từng cơn kéo dài vài tiếng rồi giảm',
          'Không bị sốt, cổ không cứng và tay chân bình thường',
        ],
      },
      {
        key: 'severity',
        label: 'Chỉ số huyết áp / Triệu chứng thần kinh',
        question: 'Bạn có đo huyết áp không và có kèm nhìn mờ, buồn nôn hay tê yếu tay chân không?',
        reason: 'Kiểm tra mối liên hệ với tăng huyết áp và loại trừ dấu hiệu thần kinh khu trú.',
        quickReplies: [
          'Huyết áp 132/85 mmHg, không tê yếu tay chân',
          'Có hơi buồn nôn và chói mắt khi nhìn màn hình',
          'Không sốt, vận động và nói chuyện hoàn toàn bình thường',
        ],
      },
    ],
  },
  urinary: {
    label: 'Thận · Tiết niệu',
    coreSlots: [
      {
        key: 'duration',
        label: 'Thời gian khởi phát',
        question: 'Tình trạng tiểu buốt / tiểu rắt này bắt đầu từ khi nào?',
        reason: 'Xác định diễn tiến cấp tính của nhiễm khuẩn tiết niệu.',
        quickReplies: [
          'Bắt đầu từ hôm qua tới nay',
          'Khoảng 2–3 ngày nay',
          'Đã tái đi tái lại nhiều lần',
        ],
      },
      {
        key: 'red_flag_screen',
        label: 'Sàng lọc sốt & đau hông lưng',
        question: 'Bạn có bị sốt cao, ớn lạnh hay đau nhức vùng hông lưng không?',
        reason: 'Phân biệt viêm bàng quang đơn thuần với viêm thận - bể thận cấp.',
        quickReplies: [
          'Không sốt và không đau hông lưng, chỉ tức bụng dưới',
          'Nước tiểu hơi đục nhưng không có máu tươi',
          'Có kèm đau mỏi vùng hông lưng và ớn lạnh',
        ],
      },
    ],
  },
  allergy: {
    label: 'Dị ứng · Da liễu · Miễn dịch',
    coreSlots: [
      {
        key: 'triggers',
        label: 'Tác nhân nghi ngờ (Thức ăn / Thuốc)',
        question: 'Trước khi nổi mẩn ngứa bạn có ăn hải sản, thức ăn lạ hoặc uống loại thuốc nào mới không?',
        reason: 'Xác định dị nguyên khởi phát để ngưng tiếp xúc ngay lập tức.',
        quickReplies: [
          'Vừa ăn món có tôm / hải sản khoảng 1 tiếng trước',
          'Mới uống thuốc giảm đau / kháng sinh',
          'Tiếp xúc khói bụi hoặc thời tiết thay đổi',
        ],
      },
      {
        key: 'red_flag_screen',
        label: 'Sàng lọc dấu hiệu phản vệ Độ II',
        question: 'Bạn có bị sưng môi/mí mắt, khàn tiếng, khó thở hay đau quặn bụng không?',
        reason: 'Đảm bảo an toàn tuyệt đối, loại trừ phản vệ tiến triển cần cấp cứu 115.',
        quickReplies: [
          'Không khó thở, không sưng môi và không đau bụng',
          'Chỉ nổi sẩn đỏ ngứa ngoài da ở tay và cổ',
          'Thấy hơi sưng mí mắt và ngứa tăng nhanh',
        ],
      },
    ],
  },
  musculoskeletal: {
    label: 'Cơ Xương Khớp · Cột sống',
    coreSlots: [
      {
        key: 'location',
        label: 'Vị trí & Hướng lan',
        question: 'Bạn đau khu trú tại khớp/vùng lưng hay có tê buốt lan xuống mông và chân không?',
        reason: 'Phân biệt căng cơ cơ học với chèn ép rễ thần kinh tọa (thoát vị đĩa đệm).',
        quickReplies: [
          'Đau mỏi vùng thắt lưng sau khi bê đồ nặng, không tê chân',
          'Đau thắt lưng kèm tê lan xuống mặt sau đùi và bắp chân',
          'Đau nhức các khớp gối khi vận động',
        ],
      },
      {
        key: 'duration',
        label: 'Thời gian diễn biến',
        question: 'Cơn đau cơ xương khớp này mới xuất hiện cấp tính hay đã kéo dài nhiều tháng?',
        reason: 'Định hướng nguyên nhân chấn thương cơ học cấp hay thoái hóa khớp mạn tính.',
        quickReplies: [
          'Mới đau 2–3 ngày nay',
          'Đau tái phát nhiều đợt khi ngồi lâu',
          'Không có yếu liệt chân hay rối loạn tiểu tiện',
        ],
      },
    ],
  },
  general: {
    label: 'Đa khoa · Nội tổng quát',
    coreSlots: [
      {
        key: 'duration',
        label: 'Thời gian khởi phát',
        question: 'Triệu chứng này đã xuất hiện từ khi nào và diễn biến tăng dần hay giảm dần?',
        reason: 'Thu thập mốc thời gian bệnh sử cơ bản.',
        quickReplies: [
          'Mới xuất hiện từ hôm qua (dưới 24 giờ)',
          'Khoảng 2–3 ngày nay',
          'Đã kéo dài hơn 1 tuần',
        ],
      },
      {
        key: 'severity',
        label: 'Mức độ & Triệu chứng đi kèm',
        question: 'Triệu chứng ở mức nhẹ hay vừa, có kèm sốt, sụt cân hay mệt mỏi nhiều không?',
        reason: 'Đánh giá mức độ ưu tiên thăm khám.',
        quickReplies: [
          'Mức độ nhẹ – vừa, vẫn sinh hoạt bình thường',
          'Có kèm mệt mỏi nhưng không sốt',
          'Triệu chứng tăng dần, cần tư vấn chuyên khoa khám',
        ],
      },
    ],
  },
};

export function analyzeClinicalDialogueState(
  currentMessage: string,
  history: { role: string; content: string }[] = []
): DialogueStateAnalysis {
  const allUserTexts = [
    ...history.filter((h) => h.role === 'user').map((h) => h.content),
    currentMessage,
  ].join(' . ');

  const normCurrent = normalizeVietnamese(currentMessage);
  const normAllUser = normalizeVietnamese(allUserTexts);

  // Stage 1: Deterministic Safety Red-Flag Detection
  const matchedEmergencyFlags: string[] = [];
  for (const text of [...history.filter((h) => h.role === 'user').map((h) => h.content), currentMessage]) {
    const kind = localEmergencyKind(text);
    const flag = kind === 'self_harm' ? 'Nguy cơ tự hại cần hỗ trợ ngay' : kind === 'medical' ? 'Dấu hiệu nguy hiểm do người dùng báo cáo' : null;
    if (flag && !matchedEmergencyFlags.includes(flag)) matchedEmergencyFlags.push(flag);
  }

  // Stage 2: Deterministic Domain & Prompt-Injection Guardrail
  for (const rule of OUT_OF_SCOPE_PATTERNS) {
    if (!matchedEmergencyFlags.length && rule.patterns.some((p) => normCurrent.includes(p))) {
      return {
        action: 'OUT_OF_SCOPE',
        stageNumber: 1,
        stageLabel: 'Ngoài phạm vi tư vấn Y tế',
        profileName: 'out_of_scope',
        profileLabel: 'Ngoài phạm vi tư vấn Y tế',
        collectedSlots: [],
        missingSlots: [],
        negatedFindings: [],
        emergencyFlags: [],
        outOfScopeReason: rule.reason,
        candidateHypotheses: [],
        matchedMeddiesSamples: [],
      };
    }
  }

  // Stage 3: Extract Reported Symptoms & Negated Symptoms
  const detectedSymptoms: { key: string; label: string; profile: string }[] = [];
  const negatedFindings: string[] = [];

  for (const sym of SYMPTOM_LEXICON) {
    for (const pat of sym.patterns) {
      if (normAllUser.includes(pat)) {
        if (
          normAllUser.includes(`khong ${pat}`) ||
          normAllUser.includes(`khong bi ${pat}`) ||
          normAllUser.includes(`khong co ${pat}`)
        ) {
          if (!negatedFindings.includes(`Không ${sym.label.toLowerCase()}`)) {
            negatedFindings.push(`Không ${sym.label.toLowerCase()}`);
          }
        } else if (!detectedSymptoms.some((d) => d.key === sym.key)) {
          detectedSymptoms.push(sym);
        }
        break;
      }
    }
  }

  const explicitNegations: [string, string][] = [
    ['khong kho tho', 'Không khó thở'],
    ['khong sot', 'Không sốt'],
    ['khong non', 'Không nôn ói'],
    ['khong phan den', 'Không đi ngoài phân đen'],
    ['khong cung co', 'Không cứng cổ'],
    ['khong te yeu', 'Không tê yếu tay chân'],
    ['khong dau lung', 'Không đau hông lưng'],
    ['khong sung moi', 'Không sưng phù môi/mắt'],
  ];
  for (const [pat, label] of explicitNegations) {
    if (normAllUser.includes(pat) && !negatedFindings.includes(label)) {
      negatedFindings.push(label);
    }
  }

  const primaryProfile = detectedSymptoms[0]?.profile || 'general';
  const profileConfig =
    PROFILE_METADATA[primaryProfile] || PROFILE_METADATA.general;

  const collectedSlots: DialogueSlotValue[] = [];
  if (detectedSymptoms.length > 0) {
    collectedSlots.push({
      slot: 'symptoms',
      label: 'Triệu chứng ghi nhận',
      value: detectedSymptoms.map((s) => s.label).join(', '),
    });
  }

  // Duration / Onset extraction
  const durationMatch = allUserTexts.match(
    /(\d+\s*(ngày|tiếng|giờ|tuần|tháng|hôm)|tối qua|hôm qua|sáng nay|mấy hôm nay|hai ngày nay|dưới 24 giờ)/i
  );
  if (durationMatch) {
    collectedSlots.push({
      slot: 'duration',
      label: 'Thời gian khởi phát',
      value: durationMatch[0],
    });
  }

  // Location extraction
  const locationMatch = allUserTexts.match(
    /(vùng thượng vị|thượng vị|vùng trán|thái dương|một bên thái dương|hai bên trán|sau gáy|cổ tay|cánh tay|quanh rốn|bụng dưới|hố chậu phải|hạ sườn phải|thắt lưng|hốc mắt)/i
  );
  if (locationMatch) {
    collectedSlots.push({
      slot: 'location',
      label: 'Vị trí triệu chứng',
      value: locationMatch[0],
    });
  }

  // Severity / Vital measurement extraction
  const severityMatch = allUserTexts.match(
    /(\d{2}[.,]\d\s*°?C|\d{2}\s*độ|\d{2,3}\/\d{2,3}\s*mmHg|âm ỉ|dữ dội|nhẹ|vừa|liên tục)/i
  );
  if (severityMatch) {
    collectedSlots.push({
      slot: 'severity',
      label: 'Mức độ / Chỉ số đo',
      value: severityMatch[0],
    });
  }

  // Character / Associated extraction
  const characterMatch = allUserTexts.match(
    /(đau rát|nóng rát|ho khan|ho có đờm|ợ chua|mẩn đỏ ngứa|sẩn đỏ|choáng nhẹ|theo nhịp mạch|buốt rát|rớm máu chân răng|nước tiểu hơi đục)/i
  );
  if (characterMatch) {
    collectedSlots.push({
      slot: 'character',
      label: 'Tính chất triệu chứng',
      value: characterMatch[0],
    });
    if (!collectedSlots.some((c) => c.slot === 'associated')) {
      collectedSlots.push({
        slot: 'associated',
        label: 'Dấu hiệu đi kèm',
        value: characterMatch[0],
      });
    }
  }

  // Trigger extraction
  const triggerMatch = allUserTexts.match(
    /(sau bữa tối|sau ăn|khi đói|thức khuya|ăn hải sản|vỏ tôm|súp hải sản|đứng dậy nhanh|thiếu ngủ|khi nằm xuống)/i
  );
  if (triggerMatch) {
    collectedSlots.push({
      slot: 'triggers',
      label: 'Yếu tố khởi phát / Liên quan',
      value: triggerMatch[0],
    });
  }

  if (negatedFindings.length > 0) {
    collectedSlots.push({
      slot: 'red_flag_screen',
      label: 'Sàng lọc dấu hiệu loại trừ',
      value: negatedFindings.join(', '),
    });
  }

  // Stage 4 & 5: Missing-Information Analysis & Question Planner
  const collectedSlotKeys = new Set(collectedSlots.map((c) => c.slot));
  const missingCoreObjects = profileConfig.coreSlots.filter(
    (cs) => !collectedSlotKeys.has(cs.key)
  );
  const missingSlots = missingCoreObjects.map((m) => m.label);

  let plannedQuestion: PlannedQuestion | undefined;
  if (missingCoreObjects.length > 0) {
    const topMissing = missingCoreObjects[0];
    plannedQuestion = {
      slot: topMissing.key,
      slotLabel: topMissing.label,
      questionText: topMissing.question,
      reason: topMissing.reason,
      quickReplies: topMissing.quickReplies,
    };
  }

  // Stage 6: Candidate Condition Hypotheses Scoring (Knowledge Base kb-v1 aligned with Meddies/meddies-consultant)
  const candidateHypotheses: CandidateHypothesis[] = [];
  const symptomKeys = new Set(detectedSymptoms.map((s) => s.key));
  const evidenceStrings = collectedSlots.map((c) => `${c.label}: ${c.value}`);
  const slotCompletenessBonus = Math.min(20, collectedSlots.length * 5);

  if (symptomKeys.has('dau_thuong_vi') || symptomKeys.has('o_chua') || symptomKeys.has('dau_bung')) {
    candidateHypotheses.push({
      name: 'Trào ngược dạ dày - thực quản (GERD) & Viêm niêm mạc dạ dày cấp',
      icd10: 'K21.0 / K29.1',
      matchScore: Math.min(92, 68 + slotCompletenessBonus),
      supportingEvidence:
        evidenceStrings.length > 0
          ? evidenceStrings
          : ['Đau âm ỉ hoặc nóng rát vùng thượng vị, ợ chua sau ăn'],
      missingEvidence:
        missingSlots.length > 0
          ? missingSlots
          : ['Nội soi dạ dày - thực quản hoặc test H. pylori để xác định tổn thương thực thể'],
      explanation:
        'Triệu chứng đau âm ỉ/nóng rát vùng thượng vị kèm ợ chua tăng sau bữa ăn tối hoặc khi nằm xuống là biểu hiện điển hình của trào ngược axit dịch vị.',
      referenceInfo:
        'Bệnh thường liên quan đến tăng tiết axit dạ dày, thói quen ăn tối muộn, nằm ngay sau ăn hoặc căng thẳng kéo dài. Điều trị ban đầu kết hợp thay đổi lối sống (kê cao đầu giường, chia nhỏ bữa ăn) và thuốc trung hòa/ức chế tiết axit theo chỉ định bác sĩ.',
      recommendedFacility: 'Chuyên khoa Nội Tiêu hóa — Bệnh viện Đa khoa hoặc Phòng khám Nội khoa',
      careLevel: 'routine',
    });

    candidateHypotheses.push({
      name: 'Khó tiêu chức năng (Functional Dyspepsia) / Viêm loét dạ dày - tá tràng',
      icd10: 'K30 / K27',
      matchScore: Math.min(78, 54 + slotCompletenessBonus),
      supportingEvidence:
        evidenceStrings.length > 0
          ? evidenceStrings
          : ['Đầy hơi, đau tức vùng trên rốn liên quan bữa ăn'],
      missingEvidence: [
        'Mối liên quan giữa cơn đau khi đói và sau ăn',
        'Xét nghiệm tìm vi khuẩn Helicobacter pylori (H. pylori)',
      ],
      explanation:
        'Cần phân biệt với loét dạ dày - tá tràng nếu cơn đau xuất hiện có chu kỳ khi bụng đói hoặc về đêm.',
      referenceInfo:
        'Loét dạ dày - tá tràng có thể do nhiễm vi khuẩn H. pylori hoặc sử dụng thuốc giảm đau kháng viêm NSAIDs kéo dài. Cần thăm khám sớm nếu đau kéo dài trên 2 tuần.',
      recommendedFacility: 'Chuyên khoa Nội Tiêu hóa — Bệnh viện Đa khoa',
      careLevel: 'soon',
    });
  }

  if (symptomKeys.has('sot') && symptomKeys.has('dau_hoc_mat')) {
    candidateHypotheses.push({
      name: 'Sốt xuất huyết Dengue (Cần xét nghiệm máu loại trừ sớm)',
      icd10: 'A97',
      matchScore: Math.min(94, 72 + slotCompletenessBonus),
      supportingEvidence:
        evidenceStrings.length > 0
          ? evidenceStrings
          : ['Sốt cao liên tục kèm đau nhức hai hốc mắt, đau mỏi cơ'],
      missingEvidence: [
        'Xét nghiệm Công thức máu (Tiểu cầu, Hematocrit) và kháng nguyên Dengue NS1Ag',
      ],
      explanation:
        'Sốt cao liên tục kèm đau nhức hốc mắt, đau mỏi cơ và không có ho/sổ mũi hoặc có rớm máu chân răng rất gợi ý Sốt xuất huyết Dengue.',
      referenceInfo:
        'Sốt xuất huyết Dengue trải qua 3 giai đoạn: giai đoạn sốt (ngày 1–3), giai đoạn nguy hiểm (ngày 3–7 khi sốt bắt đầu giảm nhưng dễ hạ tiểu cầu và cô đặc máu), và giai đoạn hồi phục. Tuyệt đối không dùng Ibuprofen hoặc Aspirin.',
      recommendedFacility: 'Khoa Truyền nhiễm / Khoa Khám bệnh — Bệnh viện Đa khoa (Khám trong ngày)',
      careLevel: 'urgent',
    });
  }

  if (symptomKeys.has('sot') || symptomKeys.has('dau_hong') || symptomKeys.has('ho') || symptomKeys.has('so_mui')) {
    candidateHypotheses.push({
      name: 'Viêm họng cấp / Nhiễm siêu vi đường hô hấp trên',
      icd10: 'J02.9 / J06.9',
      matchScore: Math.min(89, 65 + slotCompletenessBonus),
      supportingEvidence:
        evidenceStrings.length > 0
          ? evidenceStrings
          : ['Sốt cấp tính kèm đau rát họng khi nuốt và ho khan'],
      missingEvidence:
        missingSlots.length > 0
          ? missingSlots
          : ['Khám họng trực tiếp đánh giá giả mạc amidan và nghe phổi'],
      explanation:
        'Phù hợp với biểu hiện sốt vừa khởi phát cấp tính kèm đau rát họng, ho khan và không có dấu hiệu suy hô hấp.',
      referenceInfo:
        'Khoảng 70–80% viêm họng cấp ở người lớn do virus (Adenovirus, Rhinovirus, Cúm) và tự giới hạn sau 5–7 ngày với điều trị triệu chứng (hạ sốt Paracetamol, súc họng nước muối 0.9%, bù nước ấm).',
      recommendedFacility: 'Chuyên khoa Tai Mũi Họng hoặc Nội Hô hấp',
      careLevel: 'routine',
    });

    candidateHypotheses.push({
      name: 'Viêm amidan cấp / Viêm phế quản cấp (Cần theo dõi bội nhiễm)',
      icd10: 'J03.9 / J20.9',
      matchScore: Math.min(72, 50 + slotCompletenessBonus),
      supportingEvidence:
        evidenceStrings.length > 0
          ? evidenceStrings
          : ['Ho từng cơn, đau họng khi nuốt, sốt'],
      missingEvidence: [
        'Quan sát chấm mủ trắng trên amidan và hạch góc hàm sưng đau',
        'Tính chất đờm (trắng loãng hay vàng xanh)',
      ],
      explanation:
        'Cần lưu ý nếu sốt cao trên 39°C kéo dài quá 3 ngày hoặc ho khạc đờm đục.',
      referenceInfo:
        'Nếu có bội nhiễm vi khuẩn (như liên cầu khuẩn nhóm A), bác sĩ chuyên khoa sẽ chỉ định kháng sinh phù hợp (lưu ý tránh hoàn toàn nhóm Beta-lactam/Penicillin nếu người bệnh có tiền sử dị ứng Penicillin).',
      recommendedFacility: 'Phòng khám Tai Mũi Họng — Bệnh viện Đa khoa',
      careLevel: 'soon',
    });
  }

  if (symptomKeys.has('dau_dau') || symptomKeys.has('chong_mat') || symptomKeys.has('so_anh_sang')) {
    const isMigrainePattern =
      normAllUser.includes('mot ben') ||
      normAllUser.includes('mach dap') ||
      symptomKeys.has('so_anh_sang') ||
      symptomKeys.has('buon_non');

    candidateHypotheses.push({
      name: isMigrainePattern
        ? 'Đau nửa đầu (Migraine) / Đau đầu vận mạch'
        : 'Đau đầu do căng thẳng (Tension-Type Headache)',
      icd10: isMigrainePattern ? 'G43.9' : 'G44.2',
      matchScore: Math.min(90, 66 + slotCompletenessBonus),
      supportingEvidence:
        evidenceStrings.length > 0
          ? evidenceStrings
          : ['Đau vùng trán / thái dương kèm mỏi mắt hoặc choáng nhẹ'],
      missingEvidence:
        missingSlots.length > 0
          ? missingSlots
          : ['Theo dõi nhật ký cơn đau và kiểm tra thần kinh chuyên khoa'],
      explanation: isMigrainePattern
        ? 'Đau nhức một bên thái dương kiểu mạch đập kèm nhạy cảm ánh sáng và buồn nôn rất đặc trưng cho cơn Migraine.'
        : 'Đau âm ỉ hai bên trán - thái dương liên quan áp lực công việc, thiếu ngủ là đặc trưng của đau đầu căng thẳng.',
      referenceInfo:
        'Đau đầu nguyên phát (Tension Headache và Migraine) chiếm phần lớn các ca đau đầu ở người trưởng thành. Tuy nhiên cần loại trừ nguyên nhân thứ phát nếu đau đầu khởi phát đột ngột dữ dội hoặc kèm sốt, cứng gáy.',
      recommendedFacility: 'Chuyên khoa Nội Thần kinh — Bệnh viện Đa khoa',
      careLevel: 'routine',
    });

    candidateHypotheses.push({
      name: 'Theo dõi Tăng huyết áp / Hạ huyết áp tư thế',
      icd10: 'I10 / I95.1',
      matchScore: Math.min(76, 54 + slotCompletenessBonus),
      supportingEvidence:
        evidenceStrings.length > 0
          ? evidenceStrings
          : ['Choáng nhẹ khi đứng dậy nhanh, đau mỏi vùng đầu - gáy'],
      missingEvidence: [
        'Chỉ số huyết áp đo ở tư thế nằm và sau khi đứng dậy 3 phút',
      ],
      explanation:
        'Cảm giác choáng váng khi thay đổi tư thế đột ngột hoặc đau đầu buổi sáng cần được kiểm tra huyết áp định kỳ.',
      referenceInfo:
        'Huyết áp bình thường tối ưu dưới 120/80 mmHg; mức 130–139/85–89 mmHg là tiền tăng huyết áp cần theo dõi sát mỗi sáng - tối và giảm ăn mặn.',
      recommendedFacility: 'Chuyên khoa Tim mạch hoặc Nội Tổng quát',
      careLevel: 'soon',
    });
  }

  if (symptomKeys.has('tieu_buot')) {
    candidateHypotheses.push({
      name: 'Viêm bàng quang cấp (Nhiễm khuẩn đường tiết niệu dưới)',
      icd10: 'N30.0 / N39.0',
      matchScore: Math.min(91, 68 + slotCompletenessBonus),
      supportingEvidence:
        evidenceStrings.length > 0
          ? evidenceStrings
          : ['Tiểu buốt, tiểu rắt nhiều lần, tức vùng bụng dưới'],
      missingEvidence:
        missingSlots.length > 0
          ? missingSlots
          : ['Xét nghiệm Tổng phân tích nước tiểu (bạch cầu niệu, nitrit)'],
      explanation:
        'Hội chứng kích thích bàng quang (tiểu buốt, tiểu rắt, tức hạ vị) không kèm sốt cao là biểu hiện điển hình của nhiễm khuẩn tiết niệu dưới.',
      referenceInfo:
        'Bệnh cần được xét nghiệm nước tiểu tại cơ sở y tế để dùng đúng phác đồ kháng sinh đường niệu, đồng thời uống đủ 2–2.5 lít nước/ngày.',
      recommendedFacility: 'Chuyên khoa Thận - Tiết niệu — Bệnh viện Đa khoa',
      careLevel: 'soon',
    });
  }

  if (symptomKeys.has('noi_man_ngua')) {
    candidateHypotheses.push({
      name: 'Mày đay dị ứng cấp tính (Nghi do dị nguyên thực phẩm / thuốc)',
      icd10: 'L50.0',
      matchScore: Math.min(92, 69 + slotCompletenessBonus),
      supportingEvidence:
        evidenceStrings.length > 0
          ? evidenceStrings
          : ['Nổi sẩn mẩn đỏ ngứa da khởi phát cấp sau ăn'],
      missingEvidence:
        missingSlots.length > 0
          ? missingSlots
          : ['Theo dõi sát dấu hiệu phù mạch và hô hấp trong 24 giờ đầu'],
      explanation:
        'Sẩn phù đỏ ngứa xuất hiện nhanh sau bữa ăn (đặc biệt trên cơ địa dị ứng hải sản) là phản ứng quá mẫn qua trung gian Histamin.',
      referenceInfo:
        'Mày đay cấp Độ I chỉ biểu hiện ngoài da; tuy nhiên bắt buộc phải theo dõi sát các dấu hiệu Phản vệ Độ II (sưng môi mắt, khàn tiếng, khó thở, đau quặn bụng) để xử trí cấp cứu kịp thời.',
      recommendedFacility: 'Chuyên khoa Dị ứng - Miễn dịch lâm sàng hoặc Da liễu',
      careLevel: 'soon',
    });
  }

  if (symptomKeys.has('dau_khop') && candidateHypotheses.length === 0) {
    candidateHypotheses.push({
      name: 'Căng cơ thắt lưng cấp / Hội chứng chèn ép rễ thần kinh',
      icd10: 'M54.5 / M51.1',
      matchScore: Math.min(84, 62 + slotCompletenessBonus),
      supportingEvidence:
        evidenceStrings.length > 0
          ? evidenceStrings
          : ['Đau nhức cơ xương khớp / vùng lưng'],
      missingEvidence: missingSlots,
      explanation:
        'Đau vùng cơ xương khớp liên quan vận động, tư thế ngồi lâu hoặc bê vác nặng.',
      referenceInfo:
        'Cần nghỉ ngơi hợp lý, tránh cúi bê đồ nặng sai tư thế và đi khám chuyên khoa Cơ Xương Khớp nếu đau lan xuống chân kèm tê bì.',
      recommendedFacility: 'Chuyên khoa Cơ Xương Khớp hoặc Nội Thần kinh',
      careLevel: 'routine',
    });
  }

  if (candidateHypotheses.length === 0) {
    candidateHypotheses.push({
      name: 'Hội chứng triệu chứng nội khoa sớm (Cần thu thập thêm thông tin)',
      icd10: 'R69',
      matchScore: Math.min(60, 40 + slotCompletenessBonus),
      supportingEvidence:
        evidenceStrings.length > 0
          ? evidenceStrings
          : ['Triệu chứng ban đầu người dùng cung cấp'],
      missingEvidence:
        missingSlots.length > 0
          ? missingSlots
          : ['Vị trí cụ thể, thời gian khởi phát và triệu chứng đi kèm'],
      explanation:
        'Hệ thống đang tiến hành đặt câu hỏi bổ sung để thu thập đủ dữ kiện triệu chứng trước khi đưa ra dự đoán các bệnh có khả năng liên quan.',
      referenceInfo:
        'Trong quy trình sàng lọc y khoa chuẩn trên tập dữ liệu Meddies/meddies-consultant, việc hỏi rõ thời gian khởi phát, vị trí, mức độ và dấu hiệu loại trừ giúp hạn chế tối đa việc kết luận bệnh vội vàng.',
      recommendedFacility: 'Khoa Khám bệnh Nội Tổng quát — Cơ sở y tế gần nhất',
      careLevel: 'routine',
    });
  }

  const action: DialogueStateAnalysis['action'] =
    matchedEmergencyFlags.length > 0
      ? 'EMERGENCY'
      : collectedSlots.length >= 3
      ? 'FINALIZE'
      : 'ASK_MORE';

  const stageNumber: 1 | 2 | 3 =
    action === 'EMERGENCY' || action === 'FINALIZE'
      ? 3
      : collectedSlots.length <= 1
      ? 1
      : 2;

  const stageLabel =
    stageNumber === 1
      ? 'Bước 1/3: Tiếp nhận triệu chứng & Hỏi bệnh mở đầu'
      : stageNumber === 2
      ? 'Bước 2/3: Hỏi bổ sung thu thập thông tin còn thiếu'
      : 'Bước 3/3: Dự đoán bệnh có khả năng liên quan & Khuyến nghị y tế';

  const matchedMeddiesSamples = retrieveSimilarMeddiesDialogues(allUserTexts, 2);

  return {
    action,
    stageNumber,
    stageLabel,
    profileName: primaryProfile,
    profileLabel: profileConfig.label,
    collectedSlots,
    missingSlots,
    negatedFindings,
    emergencyFlags: matchedEmergencyFlags,
    plannedQuestion,
    candidateHypotheses: action === 'FINALIZE' ? candidateHypotheses : [],
    matchedMeddiesSamples,
  };
}

import { MedicationSlot } from '../types/health';

export interface CatalogMedicationItem {
  id: string;
  displayName: string;
  brandName: string;
  activeIngredient: string;
  category:
    | 'Giảm đau · Hạ sốt'
    | 'Dạ dày · Tiêu hóa'
    | 'Kháng sinh'
    | 'Tim mạch · Huyết áp'
    | 'Tiểu đường · Mỡ máu'
    | 'Hô hấp · Dị ứng'
    | 'Vitamin · Bổ trợ';
  defaultDosage: string;
  defaultInstructions: string;
  defaultPurpose: string;
  defaultSlots: MedicationSlot[];
  keywords: string[];
  cautionNote?: string;
}

export const MEDICATION_CATEGORIES = [
  'Tất cả',
  'Giảm đau · Hạ sốt',
  'Dạ dày · Tiêu hóa',
  'Kháng sinh',
  'Tim mạch · Huyết áp',
  'Tiểu đường · Mỡ máu',
  'Hô hấp · Dị ứng',
  'Vitamin · Bổ trợ',
] as const;

export const MEDICATION_CATALOG: CatalogMedicationItem[] = [
  // 1. Giảm đau · Hạ sốt · Kháng viêm
  {
    id: 'cat-paracetamol-500',
    displayName: 'Paracetamol 500mg (Efferalgan / Hapacol)',
    brandName: 'Efferalgan / Hapacol',
    activeIngredient: 'Paracetamol 500mg',
    category: 'Giảm đau · Hạ sốt',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống sau ăn, cách nhau ít nhất 4 - 6 giờ khi sốt > 38.5°C hoặc đau',
    defaultPurpose: 'Hạ sốt, giảm đau đầu, đau cơ xương khớp nhẹ',
    defaultSlots: ['Sáng', 'Chiều'],
    keywords: ['ha sot', 'giam dau', 'dau dau', 'acetaminophen', 'panadol', 'efferalgan', 'hapacol'],
  },
  {
    id: 'cat-panadol-extra',
    displayName: 'Panadol Extra (Paracetamol 500mg + Caffeine 65mg)',
    brandName: 'Panadol Extra',
    activeIngredient: 'Paracetamol 500mg + Caffeine 65mg',
    category: 'Giảm đau · Hạ sốt',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống sau ăn, tránh uống buổi tối vì có Caffeine gây mất ngủ',
    defaultPurpose: 'Giảm đau đầu, đau nửa đầu, đau răng, hạ sốt',
    defaultSlots: ['Sáng', 'Trưa'],
    keywords: ['panadol do', 'caffeine', 'dau dau', 'ha sot'],
  },
  {
    id: 'cat-ibuprofen-400',
    displayName: 'Ibuprofen 400mg (Brufen / Advil)',
    brandName: 'Brufen / Advil',
    activeIngredient: 'Ibuprofen 400mg (NSAID)',
    category: 'Giảm đau · Hạ sốt',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống ngay sau khi ăn no',
    defaultPurpose: 'Kháng viêm, giảm đau khớp, đau cơ, đau bụng kinh, hạ sốt',
    defaultSlots: ['Sáng', 'Tối'],
    keywords: ['nsaid', 'khang viem', 'dau khop', 'advil', 'brufen'],
    cautionNote: 'Thận trọng: Nhóm NSAID dễ gây kích ứng/xuất huyết dạ dày',
  },
  {
    id: 'cat-meloxicam-75',
    displayName: 'Mobic 7.5mg (Meloxicam)',
    brandName: 'Mobic',
    activeIngredient: 'Meloxicam 7.5mg (NSAID)',
    category: 'Giảm đau · Hạ sốt',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống ngay sau bữa ăn',
    defaultPurpose: 'Kháng viêm, giảm đau xương khớp, thoái hóa khớp',
    defaultSlots: ['Sáng'],
    keywords: ['mobic', 'meloxicam', 'dau xuong khop', 'nsaid'],
    cautionNote: 'Thận trọng trên bệnh nhân có tiền sử viêm loét dạ dày',
  },
  {
    id: 'cat-celecoxib-200',
    displayName: 'Celebrex 200mg (Celecoxib)',
    brandName: 'Celebrex',
    activeIngredient: 'Celecoxib 200mg (COX-2)',
    category: 'Giảm đau · Hạ sốt',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống sau bữa ăn',
    defaultPurpose: 'Giảm đau kháng viêm cơ xương khớp, cột sống',
    defaultSlots: ['Sáng'],
    keywords: ['celebrex', 'celecoxib', 'dau lung', 'dau khop'],
  },

  // 2. Dạ dày · Tiêu hóa
  {
    id: 'cat-esomeprazole-20',
    displayName: 'Esomeprazole 20mg (Nexium Mups)',
    brandName: 'Nexium Mups',
    activeIngredient: 'Esomeprazole 20mg (PPI)',
    category: 'Dạ dày · Tiêu hóa',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống nguyên viên trước bữa ăn sáng 30 phút',
    defaultPurpose: 'Giảm tiết axit dạ dày, điều trị trào ngược (GERD) & viêm loét dạ dày',
    defaultSlots: ['Sáng'],
    keywords: ['da day', 'trao nguoc', 'nexium', 'ppi', 'o chua', 'thuong vi'],
  },
  {
    id: 'cat-omeprazole-20',
    displayName: 'Omeprazole 20mg (Losec)',
    brandName: 'Losec',
    activeIngredient: 'Omeprazole 20mg (PPI)',
    category: 'Dạ dày · Tiêu hóa',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống trước ăn sáng 30 phút',
    defaultPurpose: 'Ức chế axit dịch vị, bảo vệ niêm mạc dạ dày',
    defaultSlots: ['Sáng'],
    keywords: ['omeprazol', 'da day', 'losec', 'ppi'],
  },
  {
    id: 'cat-phosphalugel',
    displayName: 'Phosphalugel 20g (Thuốc dạ dày chữ P)',
    brandName: 'Phosphalugel',
    activeIngredient: 'Colloidal Aluminium Phosphate',
    category: 'Dạ dày · Tiêu hóa',
    defaultDosage: '1 gói',
    defaultInstructions: 'Uống sau ăn 1 - 2 giờ hoặc ngay khi đau rát thượng vị',
    defaultPurpose: 'Trung hòa axit dạ dày, giảm đau rát và ợ chua nhanh',
    defaultSlots: ['Trưa', 'Tối'],
    keywords: ['goi chu p', 'antacid', 'dau da day', 'phosphalugel'],
  },
  {
    id: 'cat-gaviscon',
    displayName: 'Gaviscon Dual Action (Hỗn dịch gói 10ml)',
    brandName: 'Gaviscon',
    activeIngredient: 'Sodium Alginate + Sodium Bicarbonate + Calcium Carbonate',
    category: 'Dạ dày · Tiêu hóa',
    defaultDosage: '1 gói',
    defaultInstructions: 'Uống sau bữa ăn và trước khi đi ngủ',
    defaultPurpose: 'Tạo màng ngăn trào ngược axit dạ dày - thực quản',
    defaultSlots: ['Trưa', 'Tối'],
    keywords: ['gaviscon', 'trao nguoc', 'o nong', 'da day'],
  },
  {
    id: 'cat-domperidone-10',
    displayName: 'Motilium-M 10mg (Domperidone)',
    brandName: 'Motilium-M',
    activeIngredient: 'Domperidone 10mg',
    category: 'Dạ dày · Tiêu hóa',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống trước bữa ăn 15 - 30 phút',
    defaultPurpose: 'Giảm đầy bụng, khó tiêu, buồn nôn và nôn',
    defaultSlots: ['Sáng', 'Tối'],
    keywords: ['motilium', 'day bung', 'kho tieu', 'buon non'],
  },
  {
    id: 'cat-smecta',
    displayName: 'Smecta 3g (Diosmectite)',
    brandName: 'Smecta',
    activeIngredient: 'Diosmectite 3g',
    category: 'Dạ dày · Tiêu hóa',
    defaultDosage: '1 gói pha nước ấm',
    defaultInstructions: 'Uống xa các thuốc khác ít nhất 2 giờ',
    defaultPurpose: 'Điều trị tiêu chảy cấp và mãn tính, bảo vệ niêm mạc ruột',
    defaultSlots: ['Sáng', 'Chiều'],
    keywords: ['smecta', 'tieu chay', 'dau bung'],
  },

  // 3. Kháng sinh
  {
    id: 'cat-augmentin-1g',
    displayName: 'Augmentin 1g (Amoxicillin 875mg + Clavulanat 125mg)',
    brandName: 'Augmentin / Klamentin',
    activeIngredient: 'Amoxicillin + Acid Clavulanic (Nhóm Beta-lactam / Penicillin)',
    category: 'Kháng sinh',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống ngay đầu bữa ăn để giảm rối loạn tiêu hóa',
    defaultPurpose: 'Kháng sinh điều trị nhiễm khuẩn hô hấp, tai mũi họng, tiết niệu',
    defaultSlots: ['Sáng', 'Tối'],
    keywords: ['khang sinh', 'amoxicillin', 'augmentin', 'klamentin', 'penicillin', 'viem hong', 'viem xoang'],
    cautionNote: 'Cảnh báo: Chống chỉ định tuyệt đối nếu dị ứng Penicillin / Beta-lactam',
  },
  {
    id: 'cat-azithromycin-500',
    displayName: 'Zithromax 500mg (Azithromycin)',
    brandName: 'Zithromax',
    activeIngredient: 'Azithromycin 500mg (Nhóm Macrolid)',
    category: 'Kháng sinh',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống 1 lần/ngày, trước ăn 1 giờ hoặc sau ăn 2 giờ',
    defaultPurpose: 'Kháng sinh đường hô hấp (thường dùng thay thế khi dị ứng Penicillin)',
    defaultSlots: ['Sáng'],
    keywords: ['azithromycin', 'zithromax', 'khang sinh', 'macrolid', 'viem hong'],
  },
  {
    id: 'cat-cefuroxime-500',
    displayName: 'Zinnat 500mg (Cefuroxime)',
    brandName: 'Zinnat',
    activeIngredient: 'Cefuroxime axetil 500mg (Cephalosporin thế hệ 2)',
    category: 'Kháng sinh',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống ngay sau bữa ăn để tăng hấp thu',
    defaultPurpose: 'Kháng sinh điều trị viêm họng, viêm phế quản, viêm tai giữa',
    defaultSlots: ['Sáng', 'Tối'],
    keywords: ['zinnat', 'cefuroxime', 'khang sinh', 'cephalosporin'],
    cautionNote: 'Thận trọng dị ứng chéo nếu có tiền sử phản vệ với Penicillin',
  },
  {
    id: 'cat-ciprofloxacin-500',
    displayName: 'Ciprofloxacin 500mg (Ciprobay)',
    brandName: 'Ciprobay',
    activeIngredient: 'Ciprofloxacin 500mg (Nhóm Quinolon)',
    category: 'Kháng sinh',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống nhiều nước, tránh uống cùng sữa hoặc thuốc kháng axit/canxi/sắt',
    defaultPurpose: 'Kháng sinh nhiễm khuẩn tiết niệu, tiêu hóa',
    defaultSlots: ['Sáng', 'Tối'],
    keywords: ['cipro', 'quinolon', 'khang sinh', 'tiet nieu'],
  },

  // 4. Tim mạch · Huyết áp
  {
    id: 'cat-amlodipine-5',
    displayName: 'Amlodipine 5mg (Amlor / Norvasc)',
    brandName: 'Amlor / Norvasc',
    activeIngredient: 'Amlodipine 5mg (Chẹn kênh Canxi)',
    category: 'Tim mạch · Huyết áp',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống cố định một giờ vào buổi sáng sau ăn',
    defaultPurpose: 'Kiểm soát tăng huyết áp và dự phòng đau thắt ngực',
    defaultSlots: ['Sáng'],
    keywords: ['huyet ap', 'amlor', 'norvasc', 'amlodipin', 'cao huyet ap'],
  },
  {
    id: 'cat-losartan-50',
    displayName: 'Cozaar 50mg (Losartan Potassium)',
    brandName: 'Cozaar',
    activeIngredient: 'Losartan 50mg (Chẹn thụ thể Angiotensin - ARB)',
    category: 'Tim mạch · Huyết áp',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống cố định hàng ngày vào buổi sáng',
    defaultPurpose: 'Điều trị tăng huyết áp, bảo vệ thận trên bệnh nhân tiểu đường',
    defaultSlots: ['Sáng'],
    keywords: ['losartan', 'cozaar', 'huyet ap', 'tim mach'],
  },
  {
    id: 'cat-perindopril-5',
    displayName: 'Coversyl 5mg (Perindopril)',
    brandName: 'Coversyl',
    activeIngredient: 'Perindopril 5mg (Ức chế men chuyển - ACEi)',
    category: 'Tim mạch · Huyết áp',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống vào buổi sáng trước bữa ăn',
    defaultPurpose: 'Điều trị tăng huyết áp và suy tim (Lưu ý tác dụng phụ ho khan)',
    defaultSlots: ['Sáng'],
    keywords: ['coversyl', 'perindopril', 'huyet ap'],
  },
  {
    id: 'cat-bisoprolol-5',
    displayName: 'Concor 5mg (Bisoprolol)',
    brandName: 'Concor',
    activeIngredient: 'Bisoprolol fumarate 5mg (Chẹn Beta)',
    category: 'Tim mạch · Huyết áp',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống vào buổi sáng cùng hoặc sau bữa ăn, không tự ý ngưng đột ngột',
    defaultPurpose: 'Kiểm soát nhịp tim nhanh, tăng huyết áp và bệnh mạch vành',
    defaultSlots: ['Sáng'],
    keywords: ['concor', 'bisoprolol', 'nhip tim', 'huyet ap'],
  },
  {
    id: 'cat-aspirin-81',
    displayName: 'Aspirin 81mg (Aspirin pH8 / Bảo vệ tim mạch)',
    brandName: 'Aspirin 81mg',
    activeIngredient: 'Acetylsalicylic Acid 81mg',
    category: 'Tim mạch · Huyết áp',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống ngay sau bữa ăn no',
    defaultPurpose: 'Chống kết tập tiểu cầu, dự phòng huyết khối và đột quỵ',
    defaultSlots: ['Trưa'],
    keywords: ['aspirin', 'tim mach', 'chong dong', 'tieu cau'],
    cautionNote: 'Thận trọng: Tăng nguy cơ chảy máu dạ dày, đặc biệt khi dùng chung với NSAID',
  },
  {
    id: 'cat-clopidogrel-75',
    displayName: 'Plavix 75mg (Clopidogrel)',
    brandName: 'Plavix',
    activeIngredient: 'Clopidogrel 75mg',
    category: 'Tim mạch · Huyết áp',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống sau ăn hàng ngày',
    defaultPurpose: 'Chống kết tập tiểu cầu, dự phòng nhồi máu cơ tim & đột quỵ',
    defaultSlots: ['Sáng'],
    keywords: ['plavix', 'clopidogrel', 'tim mach', 'stent'],
  },

  // 5. Tiểu đường · Mỡ máu
  {
    id: 'cat-metformin-500',
    displayName: 'Glucophage XR 500mg (Metformin)',
    brandName: 'Glucophage XR',
    activeIngredient: 'Metformin hydrochloride 500mg',
    category: 'Tiểu đường · Mỡ máu',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống ngay trong hoặc cuối bữa ăn tối để giảm tác dụng phụ tiêu hóa',
    defaultPurpose: 'Kiểm soát đường huyết cho bệnh nhân đái tháo đường tuýp 2 / tiền tiểu đường',
    defaultSlots: ['Tối'],
    keywords: ['tieu duong', 'duong huyet', 'metformin', 'glucophage'],
  },
  {
    id: 'cat-rosuvastatin-10',
    displayName: 'Crestor 10mg (Rosuvastatin)',
    brandName: 'Crestor',
    activeIngredient: 'Rosuvastatin 10mg (Nhóm Statin)',
    category: 'Tiểu đường · Mỡ máu',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống 1 lần/ngày vào buổi tối',
    defaultPurpose: 'Hạ Cholesterol máu (LDL-C) và dự phòng xơ vữa động mạch',
    defaultSlots: ['Tối'],
    keywords: ['mo mau', 'cholesterol', 'crestor', 'rosuvastatin', 'statin'],
  },
  {
    id: 'cat-atorvastatin-20',
    displayName: 'Lipitor 20mg (Atorvastatin)',
    brandName: 'Lipitor',
    activeIngredient: 'Atorvastatin 20mg (Nhóm Statin)',
    category: 'Tiểu đường · Mỡ máu',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống vào buổi tối, tránh uống cùng nước bưởi chùm',
    defaultPurpose: 'Điều trị rối loạn mỡ máu, hạ LDL-Cholesterol và Triglyceride',
    defaultSlots: ['Tối'],
    keywords: ['lipitor', 'atorvastatin', 'mo mau', 'statin'],
  },
  {
    id: 'cat-fenofibrate-145',
    displayName: 'Lipanthyl NT 145mg (Fenofibrate)',
    brandName: 'Lipanthyl NT',
    activeIngredient: 'Fenofibrate 145mg',
    category: 'Tiểu đường · Mỡ máu',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống 1 lần/ngày vào bữa ăn chính',
    defaultPurpose: 'Hạ Triglyceride máu cao',
    defaultSlots: ['Trưa'],
    keywords: ['lipanthyl', 'fenofibrate', 'triglyceride', 'mo mau'],
  },

  // 6. Hô hấp · Dị ứng
  {
    id: 'cat-fexofenadine-180',
    displayName: 'Telfast HD 180mg (Fexofenadine)',
    brandName: 'Telfast',
    activeIngredient: 'Fexofenadine HCl 180mg (Kháng Histamin thế hệ 2)',
    category: 'Hô hấp · Dị ứng',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống với nước lọc (không uống cùng nước trái cây như cam/táo/bưởi)',
    defaultPurpose: 'Giảm viêm mũi dị ứng, hắt hơi, sổ mũi, nổi mề đay mẩn ngứa (ít gây buồn ngủ)',
    defaultSlots: ['Sáng'],
    keywords: ['di ung', 'me day', 'telfast', 'fexofenadine', 'viem mui'],
  },
  {
    id: 'cat-desloratadine-5',
    displayName: 'Aerius 5mg (Desloratadine)',
    brandName: 'Aerius',
    activeIngredient: 'Desloratadine 5mg',
    category: 'Hô hấp · Dị ứng',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống 1 lần/ngày vào buổi tối',
    defaultPurpose: 'Giảm triệu chứng viêm mũi dị ứng và mề đay ngứa da',
    defaultSlots: ['Tối'],
    keywords: ['aerius', 'desloratadin', 'di ung', 'ngua'],
  },
  {
    id: 'cat-acetylcysteine-200',
    displayName: 'Acemuc 200mg (Acetylcysteine)',
    brandName: 'Acemuc / Mitux',
    activeIngredient: 'N-Acetylcysteine 200mg',
    category: 'Hô hấp · Dị ứng',
    defaultDosage: '1 gói pha nước',
    defaultInstructions: 'Uống sau ăn kèm nhiều nước ấm để làm loãng đờm',
    defaultPurpose: 'Tiêu nhầy, loãng đờm trong viêm phế quản, ho có đờm đặc',
    defaultSlots: ['Sáng', 'Chiều'],
    keywords: ['acemuc', 'long dom', 'ho co dom', 'acetylcystein'],
    cautionNote: 'Thận trọng ở người có tiền sử viêm loét dạ dày đang tiến triển',
  },
  {
    id: 'cat-montelukast-10',
    displayName: 'Singulair 10mg (Montelukast)',
    brandName: 'Singulair',
    activeIngredient: 'Montelukast 10mg',
    category: 'Hô hấp · Dị ứng',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống vào buổi tối trước khi đi ngủ',
    defaultPurpose: 'Dự phòng hen phế quản và kiểm soát viêm mũi dị ứng',
    defaultSlots: ['Tối'],
    keywords: ['singulair', 'montelukast', 'hen suyễn', 'viem mui di ung'],
  },

  // 7. Vitamin · Bổ trợ
  {
    id: 'cat-omega3-1000',
    displayName: 'Omega-3 Fish Oil 1000mg (Dầu cá EPA/DHA)',
    brandName: 'Omega-3 Fish Oil',
    activeIngredient: 'Dầu cá tự nhiên 1000mg (EPA 180mg + DHA 120mg)',
    category: 'Vitamin · Bổ trợ',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống ngay sau bữa ăn',
    defaultPurpose: 'Hỗ trợ tim mạch, thị lực và kiểm soát Triglyceride máu',
    defaultSlots: ['Sáng', 'Tối'],
    keywords: ['omega 3', 'dau ca', 'mo mau', 'bo mat'],
  },
  {
    id: 'cat-magieb6',
    displayName: 'Magie-B6 Corbière (Magnesium + Vitamin B6)',
    brandName: 'Magne-B6 Corbière',
    activeIngredient: 'Magnesium lactat 470mg + Pyridoxin HCl (B6) 5mg',
    category: 'Vitamin · Bổ trợ',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống sau bữa ăn với nhiều nước',
    defaultPurpose: 'Giảm căng thẳng thần kinh, chuột rút cơ bắp và hỗ trợ giấc ngủ',
    defaultSlots: ['Tối'],
    keywords: ['magie b6', 'chuot rut', 'mat ngu', 'stress'],
  },
  {
    id: 'cat-vitamind3k2',
    displayName: 'Vitamin D3 1000IU + K2 (MK7)',
    brandName: 'Vitamin D3 + K2',
    activeIngredient: 'Cholecalciferol 1000IU + Menaquinone-7',
    category: 'Vitamin · Bổ trợ',
    defaultDosage: '1 viên',
    defaultInstructions: 'Uống ngay sau bữa ăn sáng (vì Vitamin D tan trong dầu)',
    defaultPurpose: 'Tăng hấp thu Canxi vào xương và nâng cao miễn dịch',
    defaultSlots: ['Sáng'],
    keywords: ['vitamin d3', 'canxi', 'loang xuong', 'mien dich'],
  },
];

/**
 * Normalizes Vietnamese accents so users can search "da day", "huyet ap", "ha sot", "khang sinh" effortlessly.
 */
export function normalizeVietnamese(str: string): string {
  return str
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .trim();
}

export function searchMedicationCatalog(
  query: string,
  categoryFilter: string = 'Tất cả',
  excludeNames: string[] = []
): CatalogMedicationItem[] {
  const normQuery = normalizeVietnamese(query);
  const excludedSet = new Set(excludeNames.map((n) => normalizeVietnamese(n)));

  return MEDICATION_CATALOG.filter((item) => {
    if (excludedSet.has(normalizeVietnamese(item.displayName))) {
      return false;
    }
    if (
      categoryFilter !== 'Tất cả' &&
      item.category !== categoryFilter
    ) {
      return false;
    }
    if (!normQuery) return true;

    const searchableText = normalizeVietnamese(
      `${item.displayName} ${item.brandName} ${item.activeIngredient} ${item.category} ${item.defaultPurpose} ${item.keywords.join(' ')}`
    );
    return searchableText.includes(normQuery);
  });
}

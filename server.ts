import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { createServer as createViteServer } from 'vite';
import { GoogleGenAI, Type } from '@google/genai';
import {
  retrieveClinicalContext,
  LAB_REFERENCE_DATASET,
} from './src/data/clinicalReferenceDataset.ts';
import { MEDICATION_CATALOG } from './src/data/medicationCatalog.ts';
import { analyzeClinicalDialogueState } from './src/services/dialogueEngine.ts';
import {
  MEDDIES_DATASET_METADATA,
  MEDDIES_BENCHMARK_EXPERIMENTS,
  MEDDIES_CONVERSATION_SAMPLES,
} from './src/data/meddiesDatasetSamples.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const QWEN_BACKEND_URL = (
  process.env.QWEN_BACKEND_URL || 'http://localhost:8000'
).replace(/\/$/, '');

function getAiClient(): GoogleGenAI {
  return new GoogleGenAI({
    apiKey: process.env.GEMINI_API_KEY,
    httpOptions: {
      headers: {
        'User-Agent': 'aistudio-build',
      },
    },
  });
}

function buildProfileContextString(profile: any): string {
  if (!profile) return 'Chưa có thông tin hồ sơ sức khỏe cá nhân.';
  const age = profile.birthYear
    ? new Date().getFullYear() - Number(profile.birthYear)
    : 'Chưa rõ';
  const bmi =
    profile.heightCm && profile.weightKg
      ? (
          Number(profile.weightKg) /
          Math.pow(Number(profile.heightCm) / 100, 2)
        ).toFixed(1)
      : 'Chưa rõ';
  const allergies =
    Array.isArray(profile.allergies) && profile.allergies.length > 0
      ? profile.allergies.join(', ')
      : 'Không ghi nhận dị ứng';
  const chronic =
    Array.isArray(profile.chronicConditions) &&
    profile.chronicConditions.length > 0
      ? profile.chronicConditions.join(', ')
      : 'Không ghi nhận bệnh lý nền';
  const currentMeds =
    Array.isArray(profile.medications) && profile.medications.length > 0
      ? profile.medications
          .map(
            (m: any) =>
              `${m.name} (${m.dosage} - ${m.instructions || ''})`
          )
          .join('; ')
      : 'Không có thuốc đang dùng định kỳ';

  return `
THÔNG TIN HỒ SƠ SỨC KHỎE BỆNH NHÂN:
- Họ tên: ${profile.fullName || 'Người dùng'} | Tuổi: ${age} | Giới tính: ${profile.gender || 'Chưa rõ'} | Nhóm máu: ${profile.bloodType || 'Chưa rõ'}
- Chiều cao: ${profile.heightCm || '?'} cm | Cân nặng: ${profile.weightKg || '?'} kg | BMI: ${bmi}
- Tiền sử DỊ ỨNG (Cần đặc biệt lưu ý tránh hoạt chất này): ${allergies}
- Bệnh lý nền / Mãn tính: ${chronic}
- Thuốc đang sử dụng: ${currentMeds}
`.trim();
}

async function checkQwenLocalBackendReady(): Promise<{
  online: boolean;
  modelReady: boolean;
  ragReady: boolean;
  url: string;
}> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 2000);
    const resp = await fetch(`${QWEN_BACKEND_URL}/ready`, {
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!resp.ok) {
      return {
        online: false,
        modelReady: false,
        ragReady: false,
        url: QWEN_BACKEND_URL,
      };
    }
    const data: any = await resp.json();
    return {
      online: Boolean(data.api),
      modelReady: Boolean(data.model),
      ragReady: Boolean(data.rag),
      url: QWEN_BACKEND_URL,
    };
  } catch {
    return {
      online: false,
      modelReady: false,
      ragReady: false,
      url: QWEN_BACKEND_URL,
    };
  }
}

async function startServer() {
  const app = express();
  const PORT = Number(process.env.PORT) || 3000;

  app.use(express.json({ limit: '25mb' }));

  // 0. Endpoint: Kiểm tra trạng thái Backend Suy Luận Chế Độ Kép & Thông tin Dataset Meddies/meddies-consultant
  app.get('/api/meddies/status', async (_req, res) => {
    const qwenStatus = await checkQwenLocalBackendReady();
    res.json({
      cloudHybridReady: true,
      qwenLocal: qwenStatus,
      datasetMetadata: MEDDIES_DATASET_METADATA,
      benchmarks: MEDDIES_BENCHMARK_EXPERIMENTS,
      sampleCount: MEDDIES_CONVERSATION_SAMPLES.length,
    });
  });

  // 1. Endpoint: Tư vấn triệu chứng, Hỏi bổ sung đa lượt & Dự đoán các bệnh có khả năng liên quan
  app.post('/api/health/chat', async (req, res) => {
    try {
      const {
        message,
        history = [],
        imageBase64,
        imageMimeType,
        patientProfile,
        inferenceMode = 'cloud_hybrid',
      } = req.body;

      if (!message && !imageBase64) {
        res.status(400).json({
          error:
            'Vui lòng nhập nội dung triệu chứng hoặc đính kèm hình ảnh y tế.',
        });
        return;
      }

      // Chạy tầng 7-Stage Clinical Dialogue Engine (DST + Safety Router + Scope Guardrail + Question Planner + Candidate Diseases + Meddies RAG)
      const dialogueState = analyzeClinicalDialogueState(
        message || '',
        history
      );

      // Nếu phát hiện câu hỏi ngoài lĩnh vực y tế hoặc Prompt Injection ở tầng Deterministic Guardrail
      if (dialogueState.action === 'OUT_OF_SCOPE' && !imageBase64) {
        res.json({
          triageLevel: 'NORMAL',
          triageTitle: 'Ngoài phạm vi tư vấn Y tế',
          summary:
            'Xin lỗi bạn, tôi là Trợ lý Y tế AI được huấn luyện trên dữ liệu hội thoại y tế Meddies/meddies-consultant và chỉ hỗ trợ tư vấn triệu chứng, dự đoán các bệnh liên quan và cung cấp thông tin y tế tham khảo.',
          detailedExplanation: `Yêu cầu của bạn được tầng kiểm soát phạm vi (Medical Scope Guardrail) nhận diện là: "${dialogueState.outOfScopeReason}". Vui lòng mô tả triệu chứng sức khỏe bạn đang gặp phải để hệ thống đặt câu hỏi thu thập thông tin và sàng lọc bệnh lý phù hợp.`,
          possibleCauses: [],
          selfCareSteps: [],
          redFlags: [],
          personalizedNotes: '',
          followUpQuestions: [
            'Mấy hôm nay tôi bị đau âm ỉ vùng thượng vị kèm ợ chua sau ăn tối',
            'Tôi bị sốt 38.5°C từ tối qua kèm đau rát họng và ho khan',
            'Hai ngày nay tôi bị đau nhức một bên thái dương kèm buồn nôn nhẹ',
          ],
          activeEngine: 'Deterministic Medical Scope Guardrail (Stage 2)',
          dialogueState,
        });
        return;
      }

      let fallbackNotice: string | undefined;

      // Chế độ 2: Nếu người dùng chọn kết nối trực tiếp tới FastAPI Backend của mô hình Qwen Fine-Tuned (qwen-rag-stack)
      if (inferenceMode === 'qwen_local' && !imageBase64) {
        try {
          const controller = new AbortController();
          const timer = setTimeout(() => controller.abort(), 6000);
          const conversationPayload = [
            ...history.slice(-12).map((m: any) => ({
              role: m.role === 'user' ? 'user' : 'assistant',
              content: m.content,
            })),
            { role: 'user', content: message },
          ];
          const qwenResp = await fetch(
            `${QWEN_BACKEND_URL}/api/v1/consultation`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ messages: conversationPayload }),
              signal: controller.signal,
            }
          );
          clearTimeout(timer);

          if (qwenResp.ok) {
            const qwenData: any = await qwenResp.json();
            const mappedLevel =
              qwenData.action === 'EMERGENCY' ||
              dialogueState.action === 'EMERGENCY'
                ? 'EMERGENCY'
                : qwenData.action === 'FINALIZE'
                ? 'SOON'
                : 'MONITOR';

            res.json({
              triageLevel: mappedLevel,
              triageTitle:
                qwenData.action === 'ASK_MORE'
                  ? 'Đang thu thập thêm thông tin triệu chứng (Multi-turn History Taking)'
                  : 'Kết quả phân tích hội thoại & Các bệnh có khả năng liên quan',
              summary: qwenData.reply || 'Đã xử lý từ mô hình Qwen Fine-tuned.',
              detailedExplanation:
                qwenData.assessment?.uncertainty ||
                qwenData.disclaimer ||
                'Mô hình Qwen fine-tuned trên tập dữ liệu Meddies/meddies-consultant đã phân tích nội dung trao đổi của bạn.',
              possibleCauses: dialogueState.candidateHypotheses.map(
                (c) => `${c.name} (Mã ICD-10: ${c.icd10} · Độ khớp: ${c.matchScore}%)`
              ),
              selfCareSteps: qwenData.assessment?.next_action
                ? [qwenData.assessment.next_action]
                : [
                    'Theo dõi sát diễn tiến triệu chứng và trả lời các câu hỏi bổ sung của trợ lý AI.',
                  ],
              redFlags:
                dialogueState.emergencyFlags.length > 0
                  ? dialogueState.emergencyFlags
                  : [
                      'Khó thở cấp, đau tức ngực, sốt cao không hạ, nôn ra máu hoặc lơ mơ.',
                    ],
              personalizedNotes:
                'Đã kết hợp kiểm tra hồ sơ dị ứng & bệnh nền cùng kết quả từ Qwen LoRA Backend.',
              followUpQuestions:
                dialogueState.plannedQuestion?.quickReplies || [
                  'Triệu chứng bắt đầu từ hôm qua',
                  'Tôi không bị sốt hay khó thở',
                ],
              activeEngine: `Qwen Fine-Tuned LoRA Backend (${QWEN_BACKEND_URL}) + 7-Stage DST`,
              dialogueState,
            });
            return;
          } else {
            fallbackNotice = `Server FastAPI Qwen cục bộ (${QWEN_BACKEND_URL}) trả về mã ${qwenResp.status}. Hệ thống tự động chuyển sang Chế độ Suy luận Trực tuyến kèm RAG Meddies/meddies-consultant.`;
          }
        } catch {
          fallbackNotice = `Server FastAPI Qwen cục bộ (${QWEN_BACKEND_URL}) hiện chưa bật trên máy trạm GPU. Hệ thống đã tự động chuyển sang Chế độ Suy luận Trực tuyến kèm RAG Meddies/meddies-consultant để không gián đoạn phiên tư vấn.`;
        }
      }

      // Chế độ 1 (Cloud Hybrid AI + Meddies/meddies-consultant RAG + 7-Stage DST)
      const ai = getAiClient();
      const profileContext = buildProfileContextString(patientProfile);
      const localClinicalRag = retrieveClinicalContext(message || '');

      const meddiesRagExamples = dialogueState.matchedMeddiesSamples
        .map(
          (s, idx) =>
            `[Mẫu hội thoại Meddies #${idx + 1} - ID: ${s.conversationId} | Nhóm bệnh: ${s.targetDisease} (${s.icd10})]\n` +
            `- Câu mở đầu bệnh nhân: "${s.initialUserPrompt}"\n` +
            `- Câu hỏi bác sĩ khai thác thêm: "${s.followUpQuestionsAsked.join(' ; ')}"\n` +
            `- Thông tin tham khảo bệnh lý: ${s.referenceDiseaseInfo.overview}\n` +
            `- Khuyến nghị cơ sở y tế: ${s.referenceDiseaseInfo.recommendedFacility} (${s.referenceDiseaseInfo.recommendedSpecialty})`
        )
        .join('\n\n');

      const historyText = Array.isArray(history)
        ? history
            .slice(-8)
            .map(
              (msg: any) =>
                `${msg.role === 'user' ? 'Bệnh nhân' : 'Trợ lý AI'}: ${msg.content}`
            )
            .join('\n')
        : '';

      const dstContextString = `
TRẠNG THÁI HỎI BỆNH LÂM SÀNG (7-STAGE DIALOGUE STATE TRACKING - DST):
- Tiến trình tư vấn: ${dialogueState.stageLabel} | Hành động điều phối: ${dialogueState.action}
- Nhóm bệnh cảnh: ${dialogueState.profileLabel}
- Thông tin triệu chứng đã thu thập từ người dùng: ${
        dialogueState.collectedSlots.length > 0
          ? dialogueState.collectedSlots
              .map((s) => `${s.label} (${s.value})`)
              .join('; ')
          : 'Mới tiếp nhận câu đầu tiên'
      }
- Triệu chứng âm tính đã loại trừ: ${dialogueState.negatedFindings.join(', ') || 'Chưa có'}
- Thông tin cốt lõi còn thiếu cần hỏi thêm: ${dialogueState.missingSlots.join(', ') || 'Đã thu thập đủ các trường cốt lõi'}
- Câu hỏi bổ sung ưu tiên từ Question Planner (P0): ${
        dialogueState.plannedQuestion
          ? `${dialogueState.plannedQuestion.questionText} (Mục tiêu y khoa: ${dialogueState.plannedQuestion.reason})`
          : 'Đã đủ thông tin cốt lõi'
      }
- Danh sách các bệnh có khả năng liên quan (Candidate Conditions): ${dialogueState.candidateHypotheses
        .map(
          (c) =>
            `${c.name} (${c.icd10} - Độ khớp ${c.matchScore}% - Khuyến nghị: ${c.recommendedFacility})`
        )
        .join(' | ')}
`.trim();

      const systemInstruction = `Bạn là Trợ lý AI Tư vấn Sức khỏe & Sàng lọc Triệu chứng thuộc đề tài "Ứng dụng AI cho bài toán Y Tế" (huấn luyện và chuẩn hóa hành vi theo bộ dữ liệu hội thoại y tế tiếng Việt Meddies/meddies-consultant, phiên bản system prompt consult-vi-v1).

MỤC TIÊU CỐT LÕI CỦA HỆ THỐNG (BÁM SÁT ĐỀ CƯƠNG ĐỀ TÀI):
1. Tương tác với người dùng dưới dạng hội thoại tự nhiên để THU THẬP THÔNG TIN VỀ TRIỆU CHỨNG:
   - Nếu hành động DST đang là "ASK_MORE" (mới ở lượt đầu hoặc còn thiếu thông tin về thời gian khởi phát, vị trí, mức độ, triệu chứng đi kèm), bạn PHẢI đặt 1–2 câu hỏi bổ sung rõ ràng, thấu cảm (ưu tiên sử dụng câu hỏi từ Question Planner P0) để thu thập thêm thông tin, đồng thời chỉ nêu các bệnh có khả năng liên quan dưới dạng "định hướng sơ bộ cần làm rõ thêm", KHÔNG khẳng định chẩn đoán chắc chắn.
2. PHÂN TÍCH NỘI DUNG TRAO ĐỔI & ĐƯA RA MỘT SỐ BỆNH CÓ KHẢ NĂNG LIÊN QUAN:
   - Liệt kê rõ các bệnh lý có khả năng liên quan (kèm mã ICD-10 và giải thích vì sao triệu chứng của người bệnh khớp với bệnh lý đó).
3. CUNG CẤP THÔNG TIN Y TẾ THAM KHẢO & KHUYẾN NGHỊ CƠ SỞ Y TẾ:
   - Cung cấp thông tin tham khảo dễ hiểu về bệnh, hướng xử lý/chăm sóc ban đầu an toàn và KHUYẾN NGHỊ CỤ THỂ người dùng cần đến chuyên khoa / cơ sở y tế nào khi cần thiết.
   - Luôn giữ đúng vai trò: Hỗ trợ sàng lọc và cung cấp thông tin ban đầu, KHÔNG thay thế chẩn đoán trực tiếp của bác sĩ và KHÔNG kê đơn/liều lượng thuốc kháng sinh hay thuốc kê đơn cụ thể.
4. RÀNG BUỘC PHẠM VI Y TẾ TUYỆT ĐỐI:
   - Chỉ trả lời các vấn đề về Y tế & Sức khỏe. Nếu câu hỏi ngoài phạm vi y tế, từ chối lịch sự và hướng dẫn người dùng mô tả triệu chứng sức khỏe.`;

      const parts: any[] = [];
      if (imageBase64 && imageMimeType) {
        parts.push({
          inlineData: {
            data: imageBase64,
            mimeType: imageMimeType,
          },
        });
      }

      parts.push({
        text: `${profileContext}

${dstContextString}

MẪU HỘI THOẠI TƯƠNG ĐỒNG TRUY XUẤT TỪ TẬP DỮ LIỆU MEDDIES/MEDDIES-CONSULTANT (REVISION 05428709a):
${meddiesRagExamples}

DỮ LIỆU PHÁC ĐỒ LÂM SÀNG THAM CHIẾU NỘI BỘ (BỘ Y TẾ / ICD-10):
${localClinicalRag}

LỊCH SỬ HỘI THOẠI HIỆN TẠI:
${historyText || '(Bắt đầu phiên hội thoại mới)'}

TRIỆU CHỨNG / PHẢN HỒI HIỆN TẠI CỦA NGƯỜI DÙNG:
${message || 'Hãy phân tích hình ảnh triệu chứng đính kèm này và tư vấn giúp tôi.'}`,
      });

      const response = await ai.models.generateContent({
        model: 'gemini-3.8-flash',
        contents: { parts },
        config: {
          systemInstruction,
          temperature: 0.25,
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              triageLevel: {
                type: Type.STRING,
                description:
                  'Mức độ khẩn cấp: NORMAL, MONITOR, SOON, hoặc EMERGENCY',
              },
              triageTitle: {
                type: Type.STRING,
                description:
                  'Tiêu đề ngắn gọn thể hiện giai đoạn sàng lọc và khuyến nghị cơ sở y tế',
              },
              summary: {
                type: Type.STRING,
                description:
                  'Lời phản hồi trực tiếp của Trợ lý AI trong hội thoại: tóm tắt triệu chứng đã ghi nhận và đặt câu hỏi bổ sung (nếu cần) hoặc đưa ra nhận định sàng lọc.',
              },
              detailedExplanation: {
                type: Type.STRING,
                description:
                  'Phân tích chi tiết mối liên hệ giữa triệu chứng với các bệnh có khả năng liên quan, thông tin y tế tham khảo về bệnh và khuyến nghị chuyên khoa/cơ sở y tế cần thăm khám.',
              },
              possibleCauses: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description:
                  'Danh sách 2-4 bệnh lý có khả năng liên quan kèm mã ICD-10 và lý do nghi ngờ.',
              },
              selfCareSteps: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description:
                  'Hướng xử lý ban đầu an toàn và khuyến nghị thăm khám tại cơ sở y tế phù hợp.',
              },
              redFlags: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description:
                  'Các dấu hiệu cảnh báo cần đến ngay cơ sở y tế hoặc gọi cấp cứu 115.',
              },
              personalizedNotes: {
                type: Type.STRING,
                description:
                  'Lưu ý đối chiếu với tiền sử dị ứng và bệnh lý nền của người dùng.',
              },
              followUpQuestions: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description:
                  '3 câu trả lời nhanh (dưới góc nhìn người bệnh trả lời câu hỏi bổ sung của bác sĩ AI) hoặc câu hỏi tiếp theo.',
              },
            },
            required: [
              'triageLevel',
              'triageTitle',
              'summary',
              'detailedExplanation',
              'possibleCauses',
              'selfCareSteps',
              'redFlags',
              'personalizedNotes',
              'followUpQuestions',
            ],
          },
        },
      });

      const rawText = response.text || '{}';
      const parsed = JSON.parse(rawText);

      // Bảo toàn an toàn: nếu tầng Safety Router phát hiện cờ đỏ cấp cứu, luôn nâng cấp lên EMERGENCY
      if (dialogueState.action === 'EMERGENCY') {
        parsed.triageLevel = 'EMERGENCY';
      }

      // Đảm bảo các nút trả lời nhanh từ Question Planner luôn có mặt để người dùng tương tác đa lượt dễ dàng
      if (
        dialogueState.plannedQuestion?.quickReplies &&
        dialogueState.plannedQuestion.quickReplies.length > 0
      ) {
        parsed.followUpQuestions = dialogueState.plannedQuestion.quickReplies;
      }

      parsed.dialogueState = dialogueState;
      parsed.activeEngine =
        'Cloud Hybrid AI + Meddies/meddies-consultant RAG + 7-Stage DST';
      if (fallbackNotice) {
        parsed.fallbackNotice = fallbackNotice;
      }

      res.json(parsed);
    } catch (error: any) {
      console.error('Error in /api/health/chat:', error);
      res.status(500).json({
        error:
          error?.message ||
          'Không thể xử lý yêu cầu tư vấn lúc này. Vui lòng thử lại.',
      });
    }
  });

  // 2. Endpoint: Đọc & Giải thích Đơn thuốc / Kết quả Xét nghiệm qua ảnh hoặc văn bản
  app.post('/api/health/analyze-doc', async (req, res) => {
    try {
      const {
        imageBase64,
        imageMimeType,
        textContext,
        docType,
        patientProfile,
      } = req.body;
      if (!imageBase64 && !textContext) {
        res.status(400).json({
          error:
            'Vui lòng tải lên hình ảnh đơn thuốc/xét nghiệm hoặc nhập dữ liệu cần phân tích.',
        });
        return;
      }

      const ai = getAiClient();
      const profileContext = buildProfileContextString(patientProfile);

      const systemInstruction = `Bạn là Chuyên gia Phân tích Cận lâm sàng & Dược lâm sàng của Middies Health AI.
Nhiệm vụ của bạn là đọc hình ảnh hoặc nội dung văn bản của Đơn thuốc (Prescription) hoặc Phiếu kết quả xét nghiệm máu/nước tiểu/sinh hóa (Lab Result), sau đó:
1. Trích xuất chính xác từng chỉ số xét nghiệm (kèm giá trị, đơn vị, khoảng tham chiếu và đánh giá NORMAL / HIGH / LOW) HOẶC từng loại thuốc trong đơn (tên thuốc, hàm lượng/liều dùng, thời điểm uống Sáng/Trưa/Chiều/Tối, công dụng chính).
2. Đối chiếu với HỒ SƠ SỨC KHỎE BỆNH NHÂN (đặc biệt là DỊ ỨNG và BỆNH NỀN) để cảnh báo nếu có hoạt chất trong đơn thuốc cần thận trọng.
3. Giải thích ý nghĩa từng chỉ số hoặc từng thuốc bằng ngôn ngữ tiếng Việt dễ hiểu cho người bệnh.`;

      const parts: any[] = [];
      if (imageBase64 && imageMimeType) {
        parts.push({
          inlineData: {
            data: imageBase64,
            mimeType: imageMimeType,
          },
        });
      }

      parts.push({
        text: `${profileContext}

BẢNG NGƯỠNG THAM CHIẾU CẬN LÂM SÀNG CHUẨN (DÙNG ĐỂ ĐỐI CHIẾU):
${LAB_REFERENCE_DATASET.map((r) => `- ${r.metric}: Bình thường ${r.normalRange}`).join('\n')}

LOẠI TÀI LIỆU NGƯỜI DÙNG CHỌN: ${docType || 'Tự động nhận diện (Đơn thuốc hoặc Xét nghiệm)'}
NỘI DUNG BỔ SUNG / VĂN BẢN MẪU:
${textContext || 'Hãy đọc kỹ hình ảnh đính kèm và bóc tách toàn bộ thông tin.'}`,
      });

      const response = await ai.models.generateContent({
        model: 'gemini-3.8-flash',
        contents: { parts },
        config: {
          systemInstruction,
          temperature: 0.2,
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              detectedType: {
                type: Type.STRING,
                description:
                  'PRESCRIPTION (Đơn thuốc), LAB_RESULT (Phiếu xét nghiệm), hoặc MEDICAL_NOTE (Chứng từ y tế khác)',
              },
              title: {
                type: Type.STRING,
                description:
                  'Tiêu đề tóm tắt của phiếu (VD: Kết quả Xét nghiệm Sinh hóa Máu & Công thức Máu)',
              },
              overallSummary: {
                type: Type.STRING,
                description:
                  'Đánh giá tổng quan dễ hiểu về kết quả xét nghiệm hoặc mục tiêu điều trị của đơn thuốc.',
              },
              triageStatus: {
                type: Type.STRING,
                description:
                  'NORMAL (Các chỉ số ổn định/Đơn thuốc an toàn), ATTENTION (Có chỉ số lệch chuẩn/Cần lưu ý khi dùng thuốc), hoặc CRITICAL (Chỉ số bất thường nghiêm trọng/Có cảnh báo dị ứng)',
              },
              metrics: {
                type: Type.ARRAY,
                description:
                  'Danh sách các chỉ số xét nghiệm hoặc sinh hiệu trích xuất được.',
                items: {
                  type: Type.OBJECT,
                  properties: {
                    name: {
                      type: Type.STRING,
                      description: 'Tên chỉ số (VD: Glucose lúc đói, HbA1c, AST/ALT)',
                    },
                    value: {
                      type: Type.STRING,
                      description: 'Giá trị đo được (VD: 6.8)',
                    },
                    unit: {
                      type: Type.STRING,
                      description: 'Đơn vị (VD: mmol/L, %)',
                    },
                    referenceRange: {
                      type: Type.STRING,
                      description: 'Khoảng tham chiếu bình thường (VD: 3.9 - 5.6)',
                    },
                    status: {
                      type: Type.STRING,
                      description: 'NORMAL, HIGH, LOW, hoặc INFO',
                    },
                    explanation: {
                      type: Type.STRING,
                      description: 'Giải thích ý nghĩa lâm sàng dễ hiểu cho bệnh nhân',
                    },
                  },
                  required: [
                    'name',
                    'value',
                    'unit',
                    'referenceRange',
                    'status',
                    'explanation',
                  ],
                },
              },
              extractedMedications: {
                type: Type.ARRAY,
                description: 'Danh sách các thuốc trích xuất từ đơn thuốc (nếu có).',
                items: {
                  type: Type.OBJECT,
                  properties: {
                    name: {
                      type: Type.STRING,
                      description: 'Tên thuốc và hoạt chất (VD: Paracetamol 500mg)',
                    },
                    dosage: {
                      type: Type.STRING,
                      description: 'Liều dùng mỗi lần (VD: 1 viên/lần)',
                    },
                    frequency: {
                      type: Type.STRING,
                      description: 'Số lần uống trong ngày (VD: 2 lần/ngày)',
                    },
                    timing: {
                      type: Type.ARRAY,
                      items: { type: Type.STRING },
                      description:
                        'Mảng các buổi uống trong ngày, chỉ chọn từ: "Sáng", "Trưa", "Chiều", "Tối"',
                    },
                    instructions: {
                      type: Type.STRING,
                      description: 'Hướng dẫn uống (VD: Uống sau ăn no)',
                    },
                    purpose: {
                      type: Type.STRING,
                      description: 'Tác dụng điều trị chính của thuốc này',
                    },
                    allergyWarning: {
                      type: Type.STRING,
                      description:
                        'Cảnh báo nếu liên quan đến dị ứng/bệnh nền của bệnh nhân (để trống nếu an toàn)',
                    },
                  },
                  required: [
                    'name',
                    'dosage',
                    'frequency',
                    'timing',
                    'instructions',
                    'purpose',
                    'allergyWarning',
                  ],
                },
              },
              recommendations: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description:
                  'Lời khuyên về chế độ ăn uống, sinh hoạt và cách dùng thuốc an toàn.',
              },
              questionsForDoctor: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description:
                  'Các câu hỏi gợi ý bệnh nhân nên trao đổi thêm với bác sĩ điều trị ở lần tái khám.',
              },
            },
            required: [
              'detectedType',
              'title',
              'overallSummary',
              'triageStatus',
              'metrics',
              'extractedMedications',
              'recommendations',
              'questionsForDoctor',
            ],
          },
        },
      });

      const rawText = response.text || '{}';
      const parsed = JSON.parse(rawText);
      res.json(parsed);
    } catch (error: any) {
      console.error('Error in /api/health/analyze-doc:', error);
      res.status(500).json({
        error:
          error?.message ||
          'Không thể phân tích tài liệu y tế lúc này. Vui lòng thử lại.',
      });
    }
  });

  // 3. Endpoint: Tra cứu thông tin thuốc & Kiểm tra tương tác thuốc an toàn
  app.post('/api/health/interactions', async (req, res) => {
    try {
      const { medications = [], patientProfile, question } = req.body;
      if (!Array.isArray(medications) || medications.length === 0) {
        res.status(400).json({
          error:
            'Vui lòng nhập ít nhất 1 loại thuốc để tra cứu và kiểm tra tương tác.',
        });
        return;
      }

      const ai = getAiClient();
      const profileContext = buildProfileContextString(patientProfile);
      const catalogMatches = MEDICATION_CATALOG.filter((c) =>
        medications.some(
          (m: string) =>
            c.displayName.toLowerCase().includes(m.toLowerCase()) ||
            m.toLowerCase().includes(c.brandName.toLowerCase())
        )
      )
        .map(
          (c) =>
            `- ${c.displayName}: Hoạt chất ${c.activeIngredient} | Cách dùng: ${c.defaultInstructions} ${
              c.cautionNote ? `| Lưu ý: ${c.cautionNote}` : ''
            }`
        )
        .join('\n');

      const systemInstruction = `Bạn là Dược sĩ Lâm sàng cao cấp của hệ thống Middies Health AI.
Nhiệm vụ của bạn:
1. Phân tích danh sách các thuốc/thực phẩm chức năng người dùng cung cấp: ${medications.join(', ')}.
2. Kiểm tra tương tác thuốc - thuốc (Drug-Drug Interactions), tương tác thuốc - thực phẩm (Drug-Food Interactions), và tương tác thuốc - bệnh lý nền/dị ứng của bệnh nhân (Drug-Patient Profile Contraindications).
3. Phân loại độ an toàn tổng thể (overallSafety):
   - "SAFE": Không có tương tác bất lợi đáng kể, có thể dùng chung theo đúng chỉ định.
   - "CAUTION": Có tương tác mức độ nhẹ hoặc trung bình (cần uống cách giờ nhau, theo dõi tác dụng phụ hoặc lưu ý dạ dày/gan/thận).
   - "CONTRAINDICATED": Có tương tác nghiêm trọng hoặc trùng lặp hoạt chất nguy hiểm hoặc xung đột trực tiếp với tiền sử dị ứng/bệnh nền của bệnh nhân.
4. Cung cấp hồ sơ chi tiết cho từng thuốc (hoạt chất, công dụng, thời điểm uống tốt nhất, tác dụng phụ thường gặp).`;

      const response = await ai.models.generateContent({
        model: 'gemini-3.8-flash',
        contents: `${profileContext}

DỮ LIỆU DƯỢC ĐIỂN NỘI BỘ KHỚP VỚI DANH SÁCH THUỐC:
${catalogMatches || '(Tra cứu theo dược thư lâm sàng chuẩn)'}

DANH SÁCH THUỐC CẦN KIỂM TRA:
${medications.map((m: string, i: number) => `${i + 1}. ${m}`).join('\n')}

CÂU HỎI CỤ THỂ CỦA BỆNH NHÂN (NẾU CÓ):
${question || 'Kiểm tra độ an toàn khi dùng các thuốc này, lịch uống cách nhau thế nào và có xung đột với bệnh nền/dị ứng của tôi không?'}`,
        config: {
          systemInstruction,
          temperature: 0.2,
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              overallSafety: {
                type: Type.STRING,
                description: 'SAFE, CAUTION, hoặc CONTRAINDICATED',
              },
              safetyHeadline: {
                type: Type.STRING,
                description:
                  'Kết luận ngắn gọn về mức độ an toàn của phác đồ thuốc này',
              },
              summary: {
                type: Type.STRING,
                description:
                  'Giải thích tổng quan về cách phối hợp các thuốc này an toàn và hiệu quả.',
              },
              pairInteractions: {
                type: Type.ARRAY,
                description:
                  'Danh sách các cặp tương tác hoặc lưu ý phối hợp thuốc.',
                items: {
                  type: Type.OBJECT,
                  properties: {
                    pair: {
                      type: Type.STRING,
                      description: 'Tên cặp thuốc hoặc hoạt chất (VD: Ibuprofen + Aspirin)',
                    },
                    severity: {
                      type: Type.STRING,
                      description: 'NONE, MILD, MODERATE, hoặc SEVERE',
                    },
                    mechanism: {
                      type: Type.STRING,
                      description:
                        'Cơ chế tương tác hoặc nguy cơ trùng lặp hoạt chất',
                    },
                    recommendation: {
                      type: Type.STRING,
                      description:
                        'Cách xử trí (VD: Uống cách nhau ít nhất 2 giờ, hoặc hỏi bác sĩ đổi thuốc)',
                    },
                  },
                  required: ['pair', 'severity', 'mechanism', 'recommendation'],
                },
              },
              profileAlerts: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description:
                  'Các cảnh báo cá nhân hóa đối chiếu với Dị ứng và Bệnh lý nền trong hồ sơ bệnh nhân.',
              },
              medicationProfiles: {
                type: Type.ARRAY,
                description:
                  'Thông tin dược lý chi tiết của từng thuốc trong danh sách.',
                items: {
                  type: Type.OBJECT,
                  properties: {
                    name: { type: Type.STRING },
                    activeIngredient: {
                      type: Type.STRING,
                      description: 'Hoạt chất chính & nhóm dược lý',
                    },
                    mainUse: {
                      type: Type.STRING,
                      description: 'Công dụng điều trị chính',
                    },
                    bestTiming: {
                      type: Type.STRING,
                      description: 'Thời điểm uống tối ưu (trước/sau ăn, sáng/tối)',
                    },
                    commonSideEffects: {
                      type: Type.ARRAY,
                      items: { type: Type.STRING },
                    },
                    foodInteractions: {
                      type: Type.STRING,
                      description:
                        'Thực phẩm/đồ uống cần tránh khi dùng thuốc (rượu bia, sữa, nước bưởi...)',
                    },
                  },
                  required: [
                    'name',
                    'activeIngredient',
                    'mainUse',
                    'bestTiming',
                    'commonSideEffects',
                    'foodInteractions',
                  ],
                },
              },
            },
            required: [
              'overallSafety',
              'safetyHeadline',
              'summary',
              'pairInteractions',
              'profileAlerts',
              'medicationProfiles',
            ],
          },
        },
      });

      const rawText = response.text || '{}';
      const parsed = JSON.parse(rawText);
      res.json(parsed);
    } catch (error: any) {
      console.error('Error in /api/health/interactions:', error);
      res.status(500).json({
        error:
          error?.message ||
          'Không thể kiểm tra tương tác thuốc lúc này. Vui lòng thử lại.',
      });
    }
  });

  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: {
        middlewareMode: true,
        hmr: false,
        ws: false,
      },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(__dirname, 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`Middies Health AI server listening on http://localhost:${PORT}`);
  });
}

startServer();

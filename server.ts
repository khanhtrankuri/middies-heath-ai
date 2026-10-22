import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { createServer as createViteServer } from 'vite';
import { GoogleGenAI, Type } from '@google/genai';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

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
  const age = profile.birthYear ? new Date().getFullYear() - Number(profile.birthYear) : 'Chưa rõ';
  const bmi =
    profile.heightCm && profile.weightKg
      ? (Number(profile.weightKg) / Math.pow(Number(profile.heightCm) / 100, 2)).toFixed(1)
      : 'Chưa rõ';
  const allergies =
    Array.isArray(profile.allergies) && profile.allergies.length > 0
      ? profile.allergies.join(', ')
      : 'Không ghi nhận dị ứng';
  const chronic =
    Array.isArray(profile.chronicConditions) && profile.chronicConditions.length > 0
      ? profile.chronicConditions.join(', ')
      : 'Không ghi nhận bệnh lý nền';
  const currentMeds =
    Array.isArray(profile.medications) && profile.medications.length > 0
      ? profile.medications.map((m: any) => `${m.name} (${m.dosage} - ${m.instructions || ''})`).join('; ')
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

async function startServer() {
  const app = express();
  const PORT = Number(process.env.PORT) || 3000;

  app.use(express.json({ limit: '25mb' }));

  // 1. Endpoint: Tư vấn triệu chứng & Phân loại mức độ khẩn cấp (Symptom Triage & Medical Chat)
  app.post('/api/health/chat', async (req, res) => {
    try {
      const { message, history = [], imageBase64, imageMimeType, patientProfile } = req.body;
      if (!message && !imageBase64) {
        res.status(400).json({ error: 'Vui lòng nhập nội dung câu hỏi hoặc đính kèm hình ảnh y tế.' });
        return;
      }

      const ai = getAiClient();
      const profileContext = buildProfileContextString(patientProfile);

      const historyText = Array.isArray(history)
        ? history
            .slice(-8)
            .map((msg: any) => `${msg.role === 'user' ? 'Bệnh nhân' : 'Bác sĩ AI'}: ${msg.content}`)
            .join('\n')
        : '';

      const systemInstruction = `Bạn là Middies Health AI — Trợ lý Y tế Lâm sàng tận tâm, chính xác và an toàn dành cho bệnh nhân tại Việt Nam.
Nhiệm vụ của bạn:
1. Phân tích triệu chứng hoặc câu hỏi sức khỏe của người dùng kết hợp chặt chẽ với HỒ SƠ SỨC KHỎE CÁ NHÂN (đặc biệt kiểm tra tiền sử dị ứng, bệnh lý nền và thuốc đang uống).
2. Phân loại mức độ khẩn cấp y khoa (triageLevel) thành 1 trong 4 mức:
   - "EMERGENCY": Dấu hiệu nguy kịch đe dọa tính mạng (đau tức ngực dữ dội, khó thở cấp, yếu liệt nửa người/méo miệng, sốt cao co giật, xuất huyết không cầm, sốc phản vệ, ý định tự hại). Cần gọi cấp cứu 115 hoặc tới phòng cấp cứu ngay lập tức.
   - "SOON": Cần đi khám bác sĩ chuyên khoa trong vòng 24-48 giờ (sốt cao liên tục >38.5°C không hạ, đau bụng khu trú, nhiễm trùng nghi ngờ cần kháng sinh, triệu chứng ảnh hưởng sinh hoạt).
   - "MONITOR": Triệu chứng nhẹ-trung bình có thể chăm sóc và theo dõi sát tại nhà trong vài ngày, đi khám nếu không giảm.
   - "NORMAL": Câu hỏi tra cứu kiến thức y khoa, dinh dưỡng, phòng bệnh hoặc chỉ số bình thường.
3. Giải thích rõ ràng, dễ hiểu bằng tiếng Việt chuẩn y khoa nhưng gần gũi, không dùng thuật ngữ quá hàn lâm mà không giải thích.
4. Luôn nhắc nhở: Thông tin chỉ mang tính chất tham khảo và hỗ trợ quyết định y tế, không thay thế chẩn đoán trực tiếp của bác sĩ.`;

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

LỊCH SỬ HỘI THOẠI GẦN ĐÂY:
${historyText || '(Bắt đầu cuộc hội thoại mới)'}

CÂU HỎI / TRIỆU CHỨNG HIỆN TẠI CỦA BỆNH NHÂN:
${message || 'Hãy phân tích hình ảnh y tế đính kèm này và tư vấn chi tiết giúp tôi.'}`,
      });

      const response = await ai.models.generateContent({
        model: 'gemini-3.8-flash',
        contents: { parts },
        config: {
          systemInstruction,
          temperature: 0.3,
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              triageLevel: {
                type: Type.STRING,
                description: 'Mức độ khẩn cấp: NORMAL, MONITOR, SOON, hoặc EMERGENCY',
              },
              triageTitle: {
                type: Type.STRING,
                description: 'Tiêu đề ngắn gọn cho mức độ khẩn cấp (VD: Cần theo dõi tại nhà & nghỉ ngơi)',
              },
              summary: {
                type: Type.STRING,
                description: 'Tóm tắt đánh giá chính trong 2-3 câu rõ ràng, thấu cảm.',
              },
              detailedExplanation: {
                type: Type.STRING,
                description: 'Giải thích chi tiết cơ chế, nguyên nhân và lời khuyên chuyên môn (hỗ trợ xuống dòng rõ ràng).',
              },
              possibleCauses: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description: 'Danh sách 2-4 nguyên nhân hoặc tình trạng có thể liên quan (mang tính định hướng).',
              },
              selfCareSteps: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description: 'Các bước hướng dẫn chăm sóc, giảm nhẹ triệu chứng an toàn tại nhà.',
              },
              redFlags: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description: 'Các dấu hiệu cảnh báo nguy hiểm cần đến bệnh viện hoặc gọi 115 ngay.',
              },
              personalizedNotes: {
                type: Type.STRING,
                description: 'Lưu ý cá nhân hóa dựa trên tiền sử dị ứng, bệnh lý nền hoặc thuốc đang dùng trong hồ sơ bệnh nhân.',
              },
              followUpQuestions: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description: '3 câu hỏi gợi ý ngắn để người dùng có thể bấm hỏi tiếp.',
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
      res.json(parsed);
    } catch (error: any) {
      console.error('Error in /api/health/chat:', error);
      res.status(500).json({
        error: error?.message || 'Không thể xử lý yêu cầu tư vấn lúc này. Vui lòng thử lại.',
      });
    }
  });

  // 2. Endpoint: Đọc & Giải thích Đơn thuốc / Kết quả Xét nghiệm qua ảnh hoặc văn bản
  app.post('/api/health/analyze-doc', async (req, res) => {
    try {
      const { imageBase64, imageMimeType, textContext, docType, patientProfile } = req.body;
      if (!imageBase64 && !textContext) {
        res.status(400).json({ error: 'Vui lòng tải lên hình ảnh đơn thuốc/xét nghiệm hoặc nhập dữ liệu cần phân tích.' });
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
                description: 'PRESCRIPTION (Đơn thuốc), LAB_RESULT (Phiếu xét nghiệm), hoặc MEDICAL_NOTE (Chứng từ y tế khác)',
              },
              title: {
                type: Type.STRING,
                description: 'Tiêu đề tóm tắt của phiếu (VD: Kết quả Xét nghiệm Sinh hóa Máu & Công thức Máu)',
              },
              overallSummary: {
                type: Type.STRING,
                description: 'Đánh giá tổng quan dễ hiểu về kết quả xét nghiệm hoặc mục tiêu điều trị của đơn thuốc.',
              },
              triageStatus: {
                type: Type.STRING,
                description: 'NORMAL (Các chỉ số ổn định/Đơn thuốc an toàn), ATTENTION (Có chỉ số lệch chuẩn/Cần lưu ý khi dùng thuốc), hoặc CRITICAL (Chỉ số bất thường nghiêm trọng/Có cảnh báo dị ứng)',
              },
              metrics: {
                type: Type.ARRAY,
                description: 'Danh sách các chỉ số xét nghiệm hoặc sinh hiệu trích xuất được.',
                items: {
                  type: Type.OBJECT,
                  properties: {
                    name: { type: Type.STRING, description: 'Tên chỉ số (VD: Glucose lúc đói, HbA1c, AST/ALT)' },
                    value: { type: Type.STRING, description: 'Giá trị đo được (VD: 6.8)' },
                    unit: { type: Type.STRING, description: 'Đơn vị (VD: mmol/L, %)' },
                    referenceRange: { type: Type.STRING, description: 'Khoảng tham chiếu bình thường (VD: 3.9 - 5.6)' },
                    status: { type: Type.STRING, description: 'NORMAL, HIGH, LOW, hoặc INFO' },
                    explanation: { type: Type.STRING, description: 'Giải thích ý nghĩa lâm sàng dễ hiểu cho bệnh nhân' },
                  },
                  required: ['name', 'value', 'unit', 'referenceRange', 'status', 'explanation'],
                },
              },
              extractedMedications: {
                type: Type.ARRAY,
                description: 'Danh sách các thuốc trích xuất từ đơn thuốc (nếu có).',
                items: {
                  type: Type.OBJECT,
                  properties: {
                    name: { type: Type.STRING, description: 'Tên thuốc và hoạt chất (VD: Paracetamol 500mg)' },
                    dosage: { type: Type.STRING, description: 'Liều dùng mỗi lần (VD: 1 viên/lần)' },
                    frequency: { type: Type.STRING, description: 'Số lần uống trong ngày (VD: 2 lần/ngày)' },
                    timing: {
                      type: Type.ARRAY,
                      items: { type: Type.STRING },
                      description: 'Mảng các buổi uống trong ngày, chỉ chọn từ: "Sáng", "Trưa", "Chiều", "Tối"',
                    },
                    instructions: { type: Type.STRING, description: 'Hướng dẫn uống (VD: Uống sau ăn no)' },
                    purpose: { type: Type.STRING, description: 'Tác dụng điều trị chính của thuốc này' },
                    allergyWarning: { type: Type.STRING, description: 'Cảnh báo nếu liên quan đến dị ứng/bệnh nền của bệnh nhân (để trống nếu an toàn)' },
                  },
                  required: ['name', 'dosage', 'frequency', 'timing', 'instructions', 'purpose', 'allergyWarning'],
                },
              },
              recommendations: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description: 'Lời khuyên về chế độ ăn uống, sinh hoạt và cách dùng thuốc an toàn.',
              },
              questionsForDoctor: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description: 'Các câu hỏi gợi ý bệnh nhân nên trao đổi thêm với bác sĩ điều trị ở lần tái khám.',
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
        error: error?.message || 'Không thể phân tích tài liệu y tế lúc này. Vui lòng thử lại.',
      });
    }
  });

  // 3. Endpoint: Tra cứu thông tin thuốc & Kiểm tra tương tác thuốc an toàn
  app.post('/api/health/interactions', async (req, res) => {
    try {
      const { medications = [], patientProfile, question } = req.body;
      if (!Array.isArray(medications) || medications.length === 0) {
        res.status(400).json({ error: 'Vui lòng nhập ít nhất 1 loại thuốc để tra cứu và kiểm tra tương tác.' });
        return;
      }

      const ai = getAiClient();
      const profileContext = buildProfileContextString(patientProfile);

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
                description: 'Kết luận ngắn gọn về mức độ an toàn của phác đồ thuốc này',
              },
              summary: {
                type: Type.STRING,
                description: 'Giải thích tổng quan về cách phối hợp các thuốc này an toàn và hiệu quả.',
              },
              pairInteractions: {
                type: Type.ARRAY,
                description: 'Danh sách các cặp tương tác hoặc lưu ý phối hợp thuốc.',
                items: {
                  type: Type.OBJECT,
                  properties: {
                    pair: { type: Type.STRING, description: 'Tên cặp thuốc hoặc hoạt chất (VD: Ibuprofen + Aspirin)' },
                    severity: { type: Type.STRING, description: 'NONE, MILD, MODERATE, hoặc SEVERE' },
                    mechanism: { type: Type.STRING, description: 'Cơ chế tương tác hoặc nguy cơ trùng lặp hoạt chất' },
                    recommendation: { type: Type.STRING, description: 'Cách xử trí (VD: Uống cách nhau ít nhất 2 giờ, hoặc hỏi bác sĩ đổi thuốc)' },
                  },
                  required: ['pair', 'severity', 'mechanism', 'recommendation'],
                },
              },
              profileAlerts: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description: 'Các cảnh báo cá nhân hóa đối chiếu với Dị ứng và Bệnh lý nền trong hồ sơ bệnh nhân.',
              },
              medicationProfiles: {
                type: Type.ARRAY,
                description: 'Thông tin dược lý chi tiết của từng thuốc trong danh sách.',
                items: {
                  type: Type.OBJECT,
                  properties: {
                    name: { type: Type.STRING },
                    activeIngredient: { type: Type.STRING, description: 'Hoạt chất chính & nhóm dược lý' },
                    mainUse: { type: Type.STRING, description: 'Công dụng điều trị chính' },
                    bestTiming: { type: Type.STRING, description: 'Thời điểm uống tối ưu (trước/sau ăn, sáng/tối)' },
                    commonSideEffects: {
                      type: Type.ARRAY,
                      items: { type: Type.STRING },
                    },
                    foodInteractions: { type: Type.STRING, description: 'Thực phẩm/đồ uống cần tránh khi dùng thuốc (rượu bia, sữa, nước bưởi...)' },
                  },
                  required: ['name', 'activeIngredient', 'mainUse', 'bestTiming', 'commonSideEffects', 'foodInteractions'],
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
        error: error?.message || 'Không thể kiểm tra tương tác thuốc lúc này. Vui lòng thử lại.',
      });
    }
  });

  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
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

import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  ImagePlus,
  AlertTriangle,
  ShieldCheck,
  Clock,
  AlertOctagon,
  RotateCcw,
  PlusCircle,
  Trash2,
  X,
  Stethoscope,
  ArrowUpRight,
  PhoneCall,
  Building2,
  BookOpen,
  Database,
  CheckCircle2,
  HelpCircle,
} from 'lucide-react';
import {
  ChatMessage,
  ChatSession,
  InferenceEngineMode,
  PatientProfile,
  TriageLevel,
  TriageResponseData,
} from '../types/health';
import { processUploadedImage } from '../utils/imageHelper';
import { MEDDIES_CONVERSATION_SAMPLES } from '../data/meddiesDatasetSamples';

interface SymptomChatViewProps {
  sessions: ChatSession[];
  activeSessionId: string;
  onSelectSession: (id: string) => void;
  onCreateNewSession: () => void;
  onDeleteSession: (id: string) => void;
  onUpdateSessionMessages: (
    sessionId: string,
    messages: ChatMessage[],
    newTitle?: string,
    lastTriage?: TriageLevel
  ) => void;
  patientProfile: PatientProfile;
  onOpenEmergencyModal: () => void;
  inferenceMode: InferenceEngineMode;
  onChangeInferenceMode: (mode: InferenceEngineMode) => void;
  onOpenMeddiesResearchTab: () => void;
  pendingSamplePrompt?: { prompt: string; title: string } | null;
  onClearPendingSamplePrompt?: () => void;
}

const SYMPTOM_STARTERS = [
  {
    label: 'Đau âm ỉ thượng vị kèm ợ chua sau ăn tối (Tiêu hóa)',
    prompt:
      'Bác sĩ ơi, mấy hôm nay tôi hay bị đau âm ỉ vùng thượng vị kèm cảm giác nóng rát ngược lên cổ họng và ợ chua, nhất là sau bữa ăn tối hoặc khi nằm xuống.',
  },
  {
    label: 'Đau nhức một bên thái dương, chói mắt & buồn nôn (Thần kinh)',
    prompt:
      'Hai ngày nay tôi bị đau nhức một bên thái dương kiểu giật theo nhịp mạch đập, nhìn vào màn hình sáng thấy chói mắt và hơi buồn nôn.',
  },
  {
    label: 'Sốt cao 39.2°C liên tục 2 ngày kèm đau hốc mắt (Sốt / Truyền nhiễm)',
    prompt:
      'Tôi bị sốt cao 39.2 độ liên tục 2 ngày nay, đau nhức hai hốc mắt và mỏi nhức khắp cơ bắp, không bị ho hay sổ mũi.',
  },
  {
    label: 'Sốt 38.5°C kèm đau rát họng & ho khan (Hô hấp)',
    prompt:
      'Tôi bị sốt 38.5°C từ tối qua, kèm đau rát họng khi nuốt và ho khan. Với tiền sử dị ứng Penicillin của tôi thì cần lưu ý gì?',
  },
];

function getTriageConfig(level: TriageLevel) {
  switch (level) {
    case 'EMERGENCY':
      return {
        label: 'CẤP CỨU Y TẾ KHẨN CẤP (115)',
        containerClass: 'border-red-300 bg-red-50/90 text-red-950',
        headerClass: 'border-b border-red-200 bg-red-100/80 text-red-900',
        icon: AlertOctagon,
        iconColor: 'text-red-600',
      };
    case 'SOON':
      return {
        label: 'KHUYẾN NGHỊ ĐẾN CƠ SỞ Y TẾ SỚM (24 - 48H)',
        containerClass: 'border-amber-300 bg-amber-50/70 text-amber-950',
        headerClass: 'border-b border-amber-200 bg-amber-100/60 text-amber-900',
        icon: Clock,
        iconColor: 'text-amber-600',
      };
    case 'MONITOR':
      return {
        label: 'SÀNG LỌC BAN ĐẦU & THEO DÕI TRIỆU CHỨNG',
        containerClass: 'border-teal-200 bg-teal-50/40 text-slate-900',
        headerClass: 'border-b border-teal-200 bg-teal-50/90 text-teal-950',
        icon: Stethoscope,
        iconColor: 'text-teal-600',
      };
    case 'NORMAL':
    default:
      return {
        label: 'THÔNG TIN Y TẾ THAM KHẢO & DỰ PHÒNG',
        containerClass: 'border-emerald-200 bg-emerald-50/30 text-slate-900',
        headerClass:
          'border-b border-emerald-200 bg-emerald-50/80 text-emerald-950',
        icon: ShieldCheck,
        iconColor: 'text-emerald-600',
      };
  }
}

export const SymptomChatView: React.FC<SymptomChatViewProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onCreateNewSession,
  onDeleteSession,
  onUpdateSessionMessages,
  patientProfile,
  onOpenEmergencyModal,
  inferenceMode,
  onChangeInferenceMode,
  onOpenMeddiesResearchTab,
  pendingSamplePrompt,
  onClearPendingSamplePrompt,
}) => {
  const [inputText, setInputText] = useState('');
  const [attachedImage, setAttachedImage] = useState<{
    base64Data: string;
    mimeType: string;
    previewUrl: string;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [lastFailedPayload, setLastFailedPayload] = useState<{
    text: string;
    img: typeof attachedImage;
  } | null>(null);
  const [expandedSampleId, setExpandedSampleId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const activeSession =
    sessions.find((s) => s.id === activeSessionId) || sessions[0];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeSession?.messages.length, isLoading]);

  // Trigger sample prompt when navigated from MeddiesResearchView
  useEffect(() => {
    if (pendingSamplePrompt && !isLoading) {
      const { prompt } = pendingSamplePrompt;
      onClearPendingSamplePrompt?.();
      void sendMessage(prompt);
    }
  }, [pendingSamplePrompt]);

  const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setErrorMsg(null);
    try {
      const processed = await processUploadedImage(file);
      setAttachedImage(processed);
    } catch (err: any) {
      setErrorMsg(err?.message || 'Không thể tải hình ảnh lên.');
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const sendMessage = async (
    customText?: string,
    retryImage?: typeof attachedImage
  ) => {
    const textToSend = (
      customText !== undefined ? customText : inputText
    ).trim();
    const imageToSend = retryImage !== undefined ? retryImage : attachedImage;

    if ((!textToSend && !imageToSend) || isLoading || !activeSession) return;

    setErrorMsg(null);
    setLastFailedPayload(null);

    const nowTime = new Date().toLocaleTimeString('vi-VN', {
      hour: '2-digit',
      minute: '2-digit',
    });

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content:
        textToSend ||
        'Nhờ trợ lý AI phân tích giúp hình ảnh triệu chứng đính kèm này.',
      timestamp: nowTime,
      imagePreviewUrl: imageToSend?.previewUrl,
    };

    const updatedHistory = [...activeSession.messages, userMsg];
    const shouldUpdateTitle =
      activeSession.messages.length === 0 ||
      activeSession.title === 'Phiên tư vấn sức khỏe mới';
    const nextTitle = shouldUpdateTitle
      ? (textToSend || 'Phân tích hình ảnh y tế').slice(0, 46)
      : activeSession.title;

    onUpdateSessionMessages(
      activeSession.id,
      updatedHistory,
      nextTitle,
      activeSession.lastTriageLevel
    );

    if (customText === undefined) {
      setInputText('');
      setAttachedImage(null);
    }
    setIsLoading(true);

    try {
      const response = await fetch('/api/health/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMsg.content,
          history: activeSession.messages.map((m) => ({
            role: m.role,
            content: m.content,
          })),
          imageBase64: imageToSend?.base64Data,
          imageMimeType: imageToSend?.mimeType,
          patientProfile,
          inferenceMode,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Lỗi máy chủ khi phân tích triệu chứng.');
      }

      const triageData: TriageResponseData = {
        triageLevel: (['NORMAL', 'MONITOR', 'SOON', 'EMERGENCY'].includes(
          data.triageLevel
        )
          ? data.triageLevel
          : 'MONITOR') as TriageLevel,
        triageTitle: data.triageTitle || 'Đánh giá triệu chứng & Sàng lọc bệnh',
        summary: data.summary || '',
        detailedExplanation: data.detailedExplanation || '',
        possibleCauses: Array.isArray(data.possibleCauses)
          ? data.possibleCauses
          : [],
        selfCareSteps: Array.isArray(data.selfCareSteps)
          ? data.selfCareSteps
          : [],
        redFlags: Array.isArray(data.redFlags) ? data.redFlags : [],
        personalizedNotes: data.personalizedNotes || '',
        followUpQuestions: Array.isArray(data.followUpQuestions)
          ? data.followUpQuestions
          : [],
        dialogueState: data.dialogueState || undefined,
        activeEngine: data.activeEngine || undefined,
        fallbackNotice: data.fallbackNotice || undefined,
      };

      const aiMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: triageData.summary,
        timestamp: new Date().toLocaleTimeString('vi-VN', {
          hour: '2-digit',
          minute: '2-digit',
        }),
        triageData,
      };

      onUpdateSessionMessages(
        activeSession.id,
        [...updatedHistory, aiMsg],
        nextTitle,
        triageData.triageLevel
      );
    } catch (err: any) {
      setErrorMsg(
        err?.message ||
          'Kết nối tạm thời gián đoạn. Vui lòng bấm Thử gửi lại.'
      );
      setLastFailedPayload({ text: userMsg.content, img: imageToSend });
    } finally {
      setIsLoading(false);
    }
  };

  // Get latest assistant message with dialogueState for the live clinical panel
  const latestAiMsgWithState = [...(activeSession?.messages || [])]
    .reverse()
    .find((m) => m.role === 'assistant' && m.triageData?.dialogueState);

  const latestDst = latestAiMsgWithState?.triageData?.dialogueState;
  const currentStage = latestDst?.stageNumber || 1;
  const matchedSamples =
    latestDst?.matchedMeddiesSamples &&
    latestDst.matchedMeddiesSamples.length > 0
      ? latestDst.matchedMeddiesSamples
      : MEDDIES_CONVERSATION_SAMPLES.slice(0, 2);

  return (
    <div className="space-y-5">
      {/* Top 3-Step Clinical Screening Progress Bar & Dual Engine Mode Selector */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3.5">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
          <div>
            <span className="text-xs font-semibold text-teal-700">
              QUY TRÌNH SÀNG LỌC TRIỆU CHỨNG & DỰ ĐOÁN BỆNH LIÊN QUAN (MEDDIES/MEDDIES-CONSULTANT)
            </span>
            <h2 className="text-sm font-bold text-slate-900 mt-0.5">
              Hỗ trợ sàng lọc và cung cấp thông tin y tế ban đầu · Không thay thế chẩn đoán của bác sĩ
            </h2>
          </div>

          {/* Dual Engine Switcher */}
          <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-1">
            <button
              type="button"
              onClick={() => onChangeInferenceMode('cloud_hybrid')}
              className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors whitespace-nowrap ${
                inferenceMode === 'cloud_hybrid'
                  ? 'bg-white text-teal-800 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Chế độ 1: Cloud AI + RAG Meddies
            </button>
            <button
              type="button"
              onClick={() => onChangeInferenceMode('qwen_local')}
              className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors whitespace-nowrap ${
                inferenceMode === 'qwen_local'
                  ? 'bg-white text-teal-800 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Chế độ 2: Qwen Fine-Tune (FastAPI)
            </button>
          </div>
        </div>

        {/* 3-Step Visual Progress Tracker */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            {
              step: 1,
              title: '01. Tiếp nhận triệu chứng tự nhiên',
              desc: 'Bóc tách triệu chứng chính, vị trí, thời gian khởi phát',
            },
            {
              step: 2,
              title: '02. Đặt câu hỏi bổ sung làm rõ',
              desc: 'Question Planner hỏi thêm thông tin bệnh sử còn thiếu',
            },
            {
              step: 3,
              title: '03. Dự đoán bệnh & Khuyến nghị y tế',
              desc: 'Đưa ra các bệnh liên quan, thông tin tham khảo & cơ sở khám',
            },
          ].map((item) => {
            const isCompleted = currentStage >= item.step;
            const isCurrent = currentStage === item.step;
            return (
              <div
                key={item.step}
                className={`rounded-lg border p-3 transition-colors ${
                  isCurrent
                    ? 'border-teal-600 bg-teal-50/50'
                    : isCompleted
                    ? 'border-emerald-200 bg-emerald-50/30'
                    : 'border-slate-200 bg-slate-50/60'
                }`}
              >
                <div className="flex items-center justify-between text-xs font-bold">
                  <span
                    className={
                      isCurrent
                        ? 'text-teal-900'
                        : isCompleted
                        ? 'text-emerald-900'
                        : 'text-slate-600'
                    }
                  >
                    {item.title}
                  </span>
                  {isCompleted && (
                    <CheckCircle2
                      className={`h-3.5 w-3.5 shrink-0 ${
                        isCurrent ? 'text-teal-600' : 'text-emerald-600'
                      }`}
                    />
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-0.5">{item.desc}</p>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left 8 Columns: Interactive Consultation & Disease Prediction Cards */}
        <div className="lg:col-span-8 flex flex-col rounded-xl border border-slate-200 bg-white overflow-hidden">
          {/* Session Sub-bar */}
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 bg-slate-50/70 px-5 py-3.5">
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                {activeSession?.title || 'Phiên tư vấn sức khỏe'}
              </h3>
              <p className="text-xs text-slate-500">
                <span>Hồ sơ: {patientProfile.fullName}</span>
                <span aria-hidden="true"> · </span>
                <span>
                  Dị ứng:{' '}
                  {patientProfile.allergies.length > 0
                    ? patientProfile.allergies.join(', ')
                    : 'Không'}
                </span>
              </p>
            </div>
            <button
              type="button"
              onClick={onCreateNewSession}
              className="flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-100 transition-colors whitespace-nowrap shrink-0"
            >
              <PlusCircle className="h-3.5 w-3.5 text-teal-600" />
              <span>Tạo Phiên Tư Vấn Mới</span>
            </button>
          </div>

          {/* Messages Stream */}
          <div className="p-6 space-y-6 min-h-[520px] max-h-[720px] overflow-y-auto">
            {activeSession?.messages.length === 0 && (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 space-y-5">
                <div className="space-y-1.5">
                  <h3 className="text-base font-bold text-slate-900">
                    Nhập triệu chứng bằng ngôn ngữ tự nhiên để bắt đầu trao đổi với Trợ lý AI
                  </h3>
                  <p className="text-sm text-slate-600 leading-relaxed">
                    Hệ thống sẽ tiếp nhận triệu chứng, tự động đặt các câu hỏi
                    bổ sung để thu thập thông tin còn thiếu, sau đó đưa ra{' '}
                    <strong className="text-slate-900">
                      danh sách các bệnh có khả năng liên quan
                    </strong>
                    ,{' '}
                    <strong className="text-slate-900">
                      thông tin y tế tham khảo về bệnh
                    </strong>{' '}
                    và{' '}
                    <strong className="text-slate-900">
                      khuyến nghị cơ sở y tế phù hợp
                    </strong>
                    .
                  </p>
                </div>

                <div className="space-y-2">
                  <span className="text-xs font-semibold text-slate-500 block">
                    Chọn kịch bản triệu chứng mẫu từ tập dữ liệu Meddies/meddies-consultant:
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {SYMPTOM_STARTERS.map((starter, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => sendMessage(starter.prompt)}
                        className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-left text-xs font-medium text-slate-800 hover:border-teal-600 hover:bg-teal-50/30 transition-colors"
                      >
                        <span className="truncate">{starter.label}</span>
                        <ArrowUpRight className="h-3.5 w-3.5 text-teal-600 shrink-0" />
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeSession?.messages.map((msg) => {
              if (msg.role === 'user') {
                return (
                  <div key={msg.id} className="flex justify-end">
                    <div className="max-w-2xl rounded-xl bg-slate-900 px-5 py-3.5 text-white space-y-2.5">
                      {msg.imagePreviewUrl && (
                        <div className="overflow-hidden rounded-lg border border-slate-700 bg-slate-800">
                          <img
                            src={msg.imagePreviewUrl}
                            alt="Hình ảnh y tế đính kèm"
                            referrerPolicy="no-referrer"
                            className="max-h-60 w-auto object-contain"
                          />
                        </div>
                      )}
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">
                        {msg.content}
                      </p>
                      <div className="text-right text-xs text-slate-400 font-mono-tabular">
                        <span>Người bệnh</span>
                        <span aria-hidden="true"> · </span>
                        <span>{msg.timestamp}</span>
                      </div>
                    </div>
                  </div>
                );
              }

              const triage = msg.triageData;
              if (!triage) {
                return (
                  <div
                    key={msg.id}
                    className="max-w-3xl rounded-xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-800 leading-relaxed"
                  >
                    {msg.content}
                  </div>
                );
              }

              const cfg = getTriageConfig(triage.triageLevel);
              const TriageIcon = cfg.icon;
              const dst = triage.dialogueState;
              const isOutOfScope = dst?.action === 'OUT_OF_SCOPE';

              return (
                <div
                  key={msg.id}
                  className={`rounded-xl border ${cfg.containerClass} overflow-hidden`}
                >
                  {/* Triage Level Header Bar */}
                  <div
                    className={`flex flex-wrap items-center justify-between gap-3 px-5 py-3 ${cfg.headerClass}`}
                  >
                    <div className="flex items-center gap-2">
                      <TriageIcon
                        className={`h-4 w-4 shrink-0 ${cfg.iconColor}`}
                      />
                      <span className="text-xs font-bold tracking-tight">
                        {cfg.label}
                      </span>
                      <span aria-hidden="true">·</span>
                      <span className="text-xs font-semibold">
                        {triage.triageTitle}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      {triage.triageLevel === 'EMERGENCY' && (
                        <button
                          type="button"
                          onClick={onOpenEmergencyModal}
                          className="flex items-center gap-1.5 rounded-md bg-red-600 px-3 py-1 text-xs font-semibold text-white hover:bg-red-700 transition-colors whitespace-nowrap shrink-0"
                        >
                          <PhoneCall className="h-3.5 w-3.5" />
                          <span>Hướng Dẫn Cấp Cứu 115</span>
                        </button>
                      )}
                      <span className="text-xs opacity-75 font-mono-tabular">
                        {msg.timestamp}
                      </span>
                    </div>
                  </div>

                  {/* Body of Clinical Response */}
                  <div className="p-5 space-y-5 bg-white/95">
                    {triage.fallbackNotice && (
                      <div className="rounded-lg border border-amber-200 bg-amber-50/70 px-3.5 py-2 text-xs text-amber-900">
                        {triage.fallbackNotice}
                      </div>
                    )}

                    {/* Executive Summary & Detailed Analysis */}
                    <div className="space-y-2">
                      <p className="text-sm font-semibold text-slate-900 leading-relaxed">
                        {triage.summary}
                      </p>
                      <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-line">
                        {triage.detailedExplanation}
                      </p>
                    </div>

                    {/* COMPONENT 1: Follow-up Question Planner & Progress Box */}
                    {dst && !isOutOfScope && dst.plannedQuestion && (
                      <div className="rounded-lg border border-teal-200 bg-teal-50/50 p-4 space-y-2.5">
                        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                          <div className="flex items-center gap-2 font-bold text-teal-950">
                            <HelpCircle className="h-4 w-4 text-teal-700 shrink-0" />
                            <span>
                              Câu Hỏi Bổ Sung Thu Thập Thông Tin Còn Thiếu (Question Planner · {dst.plannedQuestion.slotLabel})
                            </span>
                          </div>
                          <span className="font-mono-tabular text-teal-800">
                            {dst.stageLabel}
                          </span>
                        </div>
                        <p className="text-xs font-semibold text-slate-900">
                          “{dst.plannedQuestion.questionText}”
                        </p>
                        <p className="text-xs text-slate-600">
                          Mục đích hỏi thêm: {dst.plannedQuestion.reason}
                        </p>

                        {/* Quick Answer Buttons for Multi-turn History Taking */}
                        {dst.plannedQuestion.quickReplies &&
                          dst.plannedQuestion.quickReplies.length > 0 && (
                            <div className="pt-1 space-y-1.5">
                              <span className="text-xs font-medium text-slate-600 block">
                                Chọn nhanh câu trả lời của bạn để hệ thống phân tích tiếp:
                              </span>
                              <div className="flex flex-wrap gap-2">
                                {dst.plannedQuestion.quickReplies.map(
                                  (reply, rIdx) => (
                                    <button
                                      key={rIdx}
                                      type="button"
                                      disabled={isLoading}
                                      onClick={() => sendMessage(reply)}
                                      className="rounded-lg border border-teal-300 bg-white px-3 py-1.5 text-left text-xs font-semibold text-teal-900 hover:bg-teal-600 hover:text-white transition-colors disabled:opacity-50"
                                    >
                                      + {reply}
                                    </button>
                                  )
                                )}
                              </div>
                            </div>
                          )}
                      </div>
                    )}

                    {/* COMPONENT 2 & 3: Related Candidate Diseases (with Match Score + ICD-10) & Reference Disease Info + Facility Recommendation */}
                    {dst &&
                      !isOutOfScope &&
                      dst.candidateHypotheses.length > 0 && (
                        <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-4 space-y-3.5">
                          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-2.5">
                            <div>
                              <h4 className="text-xs font-bold text-slate-900">
                                Danh Sách Các Bệnh Có Khả Năng Liên Quan & Thông Tin Y Tế Tham Khảo
                              </h4>
                              <p className="text-xs text-slate-500">
                                Dựa trên phân tích hội thoại và đối chiếu kho tri thức lâm sàng (Hỗ trợ sàng lọc, không thay thế chẩn đoán bác sĩ)
                              </p>
                            </div>
                            <span className="font-mono-tabular text-xs font-semibold text-slate-600">
                              Chuyên khoa: {dst.profileLabel}
                            </span>
                          </div>

                          <div className="space-y-3">
                            {dst.candidateHypotheses.map((cand, cIdx) => {
                              const careLabel =
                                cand.careLevel === 'urgent'
                                  ? 'Cần khám ngay trong ngày'
                                  : cand.careLevel === 'soon'
                                  ? 'Nên khám trong 1–2 ngày'
                                  : 'Theo dõi & Khám chuyên khoa khi kéo dài';
                              return (
                                <div
                                  key={cIdx}
                                  className="rounded-lg border border-slate-200 bg-white p-4 space-y-3"
                                >
                                  {/* Disease Title, ICD-10 & Match Score Bar */}
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div className="space-y-0.5">
                                      <div className="flex items-center gap-2 text-xs text-slate-500 font-mono-tabular">
                                        <span>BỆNH LIÊN QUAN #{cIdx + 1}</span>
                                        <span aria-hidden="true">·</span>
                                        <span>Mã ICD-10: {cand.icd10}</span>
                                        <span aria-hidden="true">·</span>
                                        <span className="font-semibold text-teal-700">
                                          {careLabel}
                                        </span>
                                      </div>
                                      <h5 className="text-sm font-bold text-slate-900">
                                        {cand.name}
                                      </h5>
                                    </div>

                                    <div className="text-right font-mono-tabular">
                                      <span className="text-xs text-slate-500 block">
                                        Mức độ khớp triệu chứng
                                      </span>
                                      <span className="text-sm font-bold text-teal-700">
                                        {cand.matchScore}%
                                      </span>
                                    </div>
                                  </div>

                                  {/* Progress bar for match score */}
                                  <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                                    <div
                                      className="h-full bg-teal-600 rounded-full"
                                      style={{ width: `${cand.matchScore}%` }}
                                    />
                                  </div>

                                  <p className="text-xs text-slate-700 leading-relaxed">
                                    <strong className="text-slate-900">
                                      Phân tích liên hệ triệu chứng:{' '}
                                    </strong>
                                    {cand.explanation}
                                  </p>

                                  {/* Supporting vs Missing Evidence */}
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                                    <div className="rounded border border-slate-200 bg-slate-50 p-2.5 space-y-1">
                                      <span className="font-bold text-slate-800 block">
                                        Bằng chứng triệu chứng đã khớp:
                                      </span>
                                      <ul className="space-y-0.5 text-slate-600">
                                        {cand.supportingEvidence.map(
                                          (ev, eIdx) => (
                                            <li key={eIdx}>• {ev}</li>
                                          )
                                        )}
                                      </ul>
                                    </div>

                                    <div className="rounded border border-slate-200 bg-slate-50 p-2.5 space-y-1">
                                      <span className="font-bold text-slate-800 block">
                                        Thông tin cần làm rõ / Xét nghiệm thêm:
                                      </span>
                                      <ul className="space-y-0.5 text-slate-600">
                                        {cand.missingEvidence.map(
                                          (me, mIdx) => (
                                            <li key={mIdx}>• {me}</li>
                                          )
                                        )}
                                      </ul>
                                    </div>
                                  </div>

                                  {/* Reference Disease Info & Healthcare Facility Recommendation */}
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1 border-t border-slate-100 text-xs">
                                    <div className="flex items-start gap-2 text-slate-700">
                                      <BookOpen className="h-4 w-4 text-teal-600 shrink-0 mt-0.5" />
                                      <div>
                                        <strong className="text-slate-900 block">
                                          Thông tin y tế tham khảo về bệnh:
                                        </strong>
                                        <span className="leading-relaxed">
                                          {cand.referenceInfo}
                                        </span>
                                      </div>
                                    </div>

                                    <div className="flex items-start gap-2 text-slate-700">
                                      <Building2 className="h-4 w-4 text-teal-700 shrink-0 mt-0.5" />
                                      <div>
                                        <strong className="text-slate-900 block">
                                          Khuyến nghị cơ sở y tế & Chuyên khoa:
                                        </strong>
                                        <span className="leading-relaxed font-medium text-teal-900">
                                          {cand.recommendedFacility}
                                        </span>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                    {/* Personalized Profile Context Box */}
                    {triage.personalizedNotes && !isOutOfScope && (
                      <div className="rounded-lg border border-teal-200 bg-teal-50/60 p-4 space-y-1">
                        <div className="text-xs font-bold text-teal-950">
                          Lưu ý An toàn Cá nhân hóa từ Hồ sơ của {patientProfile.fullName}
                        </div>
                        <p className="text-xs text-slate-800 leading-relaxed">
                          {triage.personalizedNotes}
                        </p>
                      </div>
                    )}

                    {/* Self Care & Action Steps */}
                    {!isOutOfScope && triage.selfCareSteps.length > 0 && (
                      <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
                        <h4 className="text-xs font-bold text-slate-900 mb-2">
                          Hướng dẫn xử lý ban đầu & Khuyến nghị thăm khám
                        </h4>
                        <ul className="space-y-1.5 text-xs text-slate-700 leading-relaxed">
                          {triage.selfCareSteps.map((step, i) => (
                            <li key={i} className="flex items-start gap-2">
                              <span className="font-mono-tabular font-semibold text-teal-700 shrink-0">
                                0{i + 1}.
                              </span>
                              <span>{step}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Red Flags Warning Section */}
                    {triage.redFlags.length > 0 && !isOutOfScope && (
                      <div className="rounded-lg border border-red-200 bg-red-50/60 p-4">
                        <div className="flex items-center gap-2 text-xs font-bold text-red-900 mb-2">
                          <AlertTriangle className="h-4 w-4 text-red-600 shrink-0" />
                          <span>
                            Dấu hiệu Cảnh báo Đỏ (Red Flags) — Cần đến cơ sở y tế cấp cứu ngay nếu có:
                          </span>
                        </div>
                        <ul className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-red-950">
                          {triage.redFlags.map((flag, i) => (
                            <li key={i} className="flex items-start gap-2">
                              <span className="font-mono-tabular font-bold text-red-600 shrink-0">
                                •
                              </span>
                              <span>{flag}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Follow-up Question Starters */}
                    {triage.followUpQuestions.length > 0 && (
                      <div className="pt-2 border-t border-slate-100 space-y-2">
                        <span className="text-xs font-medium text-slate-500 block">
                          Phản hồi nhanh hoặc đặt câu hỏi tiếp theo:
                        </span>
                        <div className="flex flex-wrap gap-2">
                          {triage.followUpQuestions.map((q, i) => (
                            <button
                              key={i}
                              type="button"
                              disabled={isLoading}
                              onClick={() => sendMessage(q)}
                              className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-left text-xs font-medium text-slate-700 hover:border-teal-600 hover:bg-teal-50/50 hover:text-slate-900 transition-colors disabled:opacity-50"
                            >
                              {q}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {triage.activeEngine && (
                      <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400 font-mono-tabular">
                        <span>Engine suy luận: {triage.activeEngine}</span>
                        <span>
                          Vai trò: Hỗ trợ sàng lọc & thông tin ban đầu · Không thay thế bác sĩ
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Skeleton / Loading state */}
            {isLoading && (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-5 space-y-3 animate-pulse">
                <div className="flex items-center justify-between">
                  <div className="h-4 w-56 rounded bg-slate-200" />
                  <div className="h-3 w-16 rounded bg-slate-200" />
                </div>
                <div className="h-4 w-full rounded bg-slate-200" />
                <div className="h-4 w-5/6 rounded bg-slate-200" />
                <div className="grid grid-cols-2 gap-4 pt-2">
                  <div className="h-20 rounded-lg bg-slate-200" />
                  <div className="h-20 rounded-lg bg-slate-200" />
                </div>
                <p className="text-xs text-teal-700 font-medium pt-1">
                  Đang thu thập thông tin triệu chứng (DST), đối chiếu tập dữ liệu Meddies/meddies-consultant và phân tích các bệnh liên quan...
                </p>
              </div>
            )}

            {/* Error Recovery Banner */}
            {errorMsg && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-2.5 text-xs text-red-900">
                  <AlertTriangle className="h-4 w-4 text-red-600 shrink-0" />
                  <span>{errorMsg}</span>
                </div>
                {lastFailedPayload && (
                  <button
                    type="button"
                    onClick={() =>
                      sendMessage(
                        lastFailedPayload.text,
                        lastFailedPayload.img
                      )
                    }
                    className="flex items-center gap-1.5 rounded-lg bg-red-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-red-700 transition-colors whitespace-nowrap shrink-0"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    <span>Thử gửi lại</span>
                  </button>
                )}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Composer */}
          <div className="border-t border-slate-200 bg-slate-50 p-4 space-y-3">
            {attachedImage && (
              <div className="flex items-center justify-between rounded-lg border border-teal-200 bg-white p-2.5">
                <div className="flex items-center gap-3">
                  <img
                    src={attachedImage.previewUrl}
                    alt="Ảnh chuẩn bị gửi"
                    referrerPolicy="no-referrer"
                    className="h-12 w-12 rounded object-cover border border-slate-200"
                  />
                  <div className="text-xs">
                    <p className="font-semibold text-slate-900">
                      Đã đính kèm hình ảnh triệu chứng / y tế
                    </p>
                    <p className="text-slate-500">
                      AI sẽ kết hợp phân tích hình ảnh và mô tả triệu chứng của bạn
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setAttachedImage(null)}
                  className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                  aria-label="Gỡ ảnh đính kèm"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}

            <div className="flex items-end gap-2.5">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleImageSelect}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading}
                className="flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-xs font-medium text-slate-700 hover:bg-slate-100 transition-colors whitespace-nowrap shrink-0 disabled:opacity-50"
                title="Đính kèm ảnh chụp triệu chứng ngoài da, nhiệt kế hoặc đơn thuốc"
              >
                <ImagePlus className="h-4 w-4 text-teal-600" />
                <span className="hidden sm:inline">Đính kèm ảnh</span>
              </button>

              <div className="relative flex-1">
                <textarea
                  rows={2}
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      void sendMessage();
                    }
                  }}
                  placeholder="Nhập các triệu chứng của bạn (VD: vị trí đau, thời gian khởi phát, mức độ, triệu chứng đi kèm)..."
                  className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-teal-600 focus:outline-none"
                />
              </div>

              <button
                type="button"
                disabled={isLoading || (!inputText.trim() && !attachedImage)}
                onClick={() => void sendMessage()}
                className="flex items-center gap-2 rounded-lg bg-teal-600 px-5 py-2.5 text-xs font-semibold text-white hover:bg-teal-700 transition-colors whitespace-nowrap shrink-0 disabled:opacity-50"
              >
                <Send className="h-4 w-4" />
                <span>Gửi & Phân tích</span>
              </button>
            </div>

            <p className="text-xs text-slate-500">
              Vai trò hệ thống: Hỗ trợ sàng lọc triệu chứng và cung cấp thông tin y tế tham khảo ban đầu, không thay thế chẩn đoán trực tiếp của bác sĩ.
            </p>
          </div>
        </div>

        {/* Right 4 Columns: Live DST Summary + Matched Meddies/meddies-consultant Samples + Session History */}
        <div className="lg:col-span-4 space-y-5">
          {/* Live Collected Symptoms & DST Card */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3.5">
            <div className="border-b border-slate-200 pb-3">
              <span className="text-xs font-semibold text-teal-700">
                TRẠNG THÁI THU THẬP TRIỆU CHỨNG (LIVE DST)
              </span>
              <h3 className="text-sm font-bold text-slate-900 mt-0.5">
                {latestDst?.profileLabel || 'Đang chờ tiếp nhận triệu chứng'}
              </h3>
              <p className="text-xs text-slate-500 font-mono-tabular mt-0.5">
                {latestDst?.stageLabel || 'Bước 1/3: Tiếp nhận triệu chứng'}
              </p>
            </div>

            {latestDst && latestDst.collectedSlots.length > 0 ? (
              <div className="space-y-2 text-xs">
                <span className="font-semibold text-slate-800 block">
                  Thông tin triệu chứng đã ghi nhận:
                </span>
                <div className="space-y-1.5">
                  {latestDst.collectedSlots.map((slot, sIdx) => (
                    <div
                      key={sIdx}
                      className="rounded border border-slate-200 bg-slate-50 px-3 py-2 flex items-start justify-between gap-2"
                    >
                      <span className="font-semibold text-slate-700 shrink-0">
                        {slot.label}:
                      </span>
                      <span className="text-slate-900 text-right">
                        {slot.value}
                      </span>
                    </div>
                  ))}
                </div>
                {latestDst.missingSlots.length > 0 && (
                  <p className="text-slate-500 pt-1">
                    <strong className="text-slate-700">Cần hỏi thêm: </strong>
                    {latestDst.missingSlots.join(' · ')}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-xs text-slate-500">
                Khi bạn mô tả triệu chứng, hệ thống sẽ tự động trích xuất vị
                trí, thời gian khởi phát, mức độ và các dấu hiệu loại trừ tại đây.
              </p>
            )}
          </div>

          {/* COMPONENT 4: Matched Conversation Samples from Meddies/meddies-consultant */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3.5">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-teal-600 shrink-0" />
                <h3 className="text-sm font-bold text-slate-900">
                  Mẫu Hội Thoại Meddies Tương Đồng
                </h3>
              </div>
              <button
                type="button"
                onClick={onOpenMeddiesResearchTab}
                className="text-xs font-semibold text-teal-700 hover:text-teal-900 whitespace-nowrap"
              >
                Xem toàn bộ Dataset →
              </button>
            </div>

            <p className="text-xs text-slate-500">
              Các ca hội thoại y tế tiếng Việt tương đồng được truy xuất từ tập
              dữ liệu{' '}
              <span className="font-mono-tabular font-semibold text-slate-700">
                Meddies/meddies-consultant
              </span>
              :
            </p>

            <div className="space-y-2.5">
              {matchedSamples.map((sample) => {
                const isExpanded = expandedSampleId === sample.id;
                return (
                  <div
                    key={sample.id}
                    className="rounded-lg border border-slate-200 bg-slate-50/70 p-3 text-xs space-y-2"
                  >
                    <div className="flex items-center justify-between font-mono-tabular text-[11px] text-slate-500">
                      <span>ID: {sample.conversationId}</span>
                      <span>ICD-10: {sample.icd10}</span>
                    </div>
                    <p className="font-bold text-slate-900">
                      {sample.targetDisease}
                    </p>
                    <p className="text-slate-600">
                      “{sample.initialUserPrompt}”
                    </p>
                    <div className="flex items-center justify-between pt-1">
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedSampleId(isExpanded ? null : sample.id)
                        }
                        className="font-semibold text-teal-700 hover:text-teal-900"
                      >
                        {isExpanded
                          ? 'Thu gọn hội thoại mẫu'
                          : 'Xem các lượt bác sĩ hỏi bệnh'}
                      </button>
                      <button
                        type="button"
                        onClick={() => sendMessage(sample.initialUserPrompt)}
                        className="font-semibold text-slate-700 hover:text-slate-900"
                      >
                        Thử câu này ↗
                      </button>
                    </div>

                    {isExpanded && (
                      <div className="pt-2 border-t border-slate-200 space-y-2">
                        {sample.messages.map((m) => (
                          <div
                            key={m.turn}
                            className="rounded border border-slate-200 bg-white p-2 text-[11px] leading-relaxed"
                          >
                            <strong className="text-slate-900">
                              {m.role === 'user' ? 'Bệnh nhân: ' : 'Bác sĩ AI: '}
                            </strong>
                            <span className="text-slate-700">{m.content}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Consultation Sessions List */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3.5">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <h3 className="text-sm font-bold text-slate-900">
                Lịch Sử Phiên Tư Vấn ({sessions.length})
              </h3>
              <button
                type="button"
                onClick={onCreateNewSession}
                className="text-xs font-semibold text-teal-700 hover:text-teal-800 whitespace-nowrap"
              >
                + Phiên mới
              </button>
            </div>

            <div className="space-y-2 max-h-64 overflow-y-auto">
              {sessions.map((s) => {
                const isSelected = s.id === activeSession?.id;
                return (
                  <div
                    key={s.id}
                    className={`group flex items-center justify-between gap-2 rounded-lg border p-3 transition-colors ${
                      isSelected
                        ? 'border-teal-600 bg-teal-50/40'
                        : 'border-slate-200 bg-white hover:bg-slate-50'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => onSelectSession(s.id)}
                      className="flex-1 text-left min-w-0"
                    >
                      <p className="text-xs font-semibold text-slate-900 truncate">
                        {s.title}
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5 font-mono-tabular">
                        <span>{s.messages.length} lượt trao đổi</span>
                        {s.lastTriageLevel && (
                          <>
                            <span aria-hidden="true"> · </span>
                            <span>Mức: {s.lastTriageLevel}</span>
                          </>
                        )}
                      </p>
                    </button>
                    {sessions.length > 1 && (
                      <button
                        type="button"
                        onClick={() => onDeleteSession(s.id)}
                        className="rounded p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600 transition-colors shrink-0"
                        title="Xóa phiên tư vấn này"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

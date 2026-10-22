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
} from 'lucide-react';
import {
  ChatMessage,
  ChatSession,
  PatientProfile,
  TriageLevel,
  TriageResponseData,
} from '../types/health';
import { processUploadedImage } from '../utils/imageHelper';

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
}

const SYMPTOM_STARTERS = [
  {
    label: 'Sốt 38.8°C kèm đau rát họng & ho khan',
    prompt:
      'Tôi bị sốt 38.8°C từ tối qua, kèm đau rát họng khi nuốt và ho khan. Với tiền sử dị ứng Penicillin của tôi thì nên chăm sóc và dùng thuốc hạ sốt thế nào cho an toàn?',
  },
  {
    label: 'Đau đầu căng thẳng & choáng nhẹ khi đứng dậy',
    prompt:
      'Hai ngày nay tôi bị đau âm ỉ vùng trán và thái dương, đôi khi đứng dậy nhanh thấy hơi choáng nhẹ. Huyết áp sáng nay đo là 132/85 mmHg. Tôi cần lưu ý gì?',
  },
  {
    label: 'Đầy bụng, nóng rát thượng vị sau ăn tối',
    prompt:
      'Sau bữa tối tôi thường bị đầy hơi, nóng rát vùng ngực và thượng vị, nằm xuống thì khó chịu hơn. Tôi nên xử trí tại nhà như thế nào?',
  },
  {
    label: 'Nổi mẩn ngứa đỏ ở cổ tay sau khi ăn hải sản',
    prompt:
      'Tôi vừa ăn tối có món súp hải sản khoảng 1 tiếng trước, hiện tại thấy nổi mẩn đỏ ngứa ở hai cổ tay nhưng không khó thở. Tôi nên theo dõi dấu hiệu gì và xử lý ra sao?',
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
        label: 'KHUYẾN NGHỊ KHÁM BÁC SĨ SỚM (24 - 48H)',
        containerClass: 'border-amber-300 bg-amber-50/70 text-amber-950',
        headerClass: 'border-b border-amber-200 bg-amber-100/60 text-amber-900',
        icon: Clock,
        iconColor: 'text-amber-600',
      };
    case 'MONITOR':
      return {
        label: 'CHĂM SÓC & THEO DÕI TẠI NHÀ',
        containerClass: 'border-teal-200 bg-teal-50/40 text-slate-900',
        headerClass: 'border-b border-teal-200 bg-teal-50/90 text-teal-950',
        icon: Stethoscope,
        iconColor: 'text-teal-600',
      };
    case 'NORMAL':
    default:
      return {
        label: 'THÔNG TIN Y KHOA & DỰ PHÒNG AN TOÀN',
        containerClass: 'border-emerald-200 bg-emerald-50/30 text-slate-900',
        headerClass: 'border-b border-emerald-200 bg-emerald-50/80 text-emerald-950',
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

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const activeSession =
    sessions.find((s) => s.id === activeSessionId) || sessions[0];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeSession?.messages.length, isLoading]);

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
    const textToSend = (customText !== undefined ? customText : inputText).trim();
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
        'Nhờ bác sĩ AI phân tích giúp hình ảnh y tế đính kèm này.',
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
        triageTitle: data.triageTitle || 'Đánh giá triệu chứng lâm sàng',
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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      {/* Main Chat & Triage Column */}
      <div className="lg:col-span-8 flex flex-col rounded-xl border border-slate-200 bg-white overflow-hidden">
        {/* Session Sub-bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 bg-slate-50/70 px-5 py-3.5">
          <div>
            <h2 className="text-base font-bold text-slate-900">
              {activeSession?.title || 'Phiên tư vấn sức khỏe'}
            </h2>
            <p className="text-xs text-slate-500">
              <span>Đã đồng bộ Hồ sơ: {patientProfile.fullName}</span>
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
            onClick={onCreateNewSession}
            className="flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-100 transition-colors whitespace-nowrap shrink-0"
          >
            <PlusCircle className="h-3.5 w-3.5 text-teal-600" />
            <span>Tạo Phiên Tư Vấn Mới</span>
          </button>
        </div>

        {/* Messages Stream */}
        <div className="p-6 space-y-6 min-h-[500px] max-h-[680px] overflow-y-auto">
          {activeSession?.messages.length === 0 && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 space-y-5">
              <div className="space-y-1.5">
                <h3 className="text-base font-bold text-slate-900">
                  Mô tả triệu chứng hoặc đính kèm hình ảnh y tế để bắt đầu
                </h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Middies Health AI sẽ tự động đối chiếu với tiền sử dị ứng (
                  <strong className="text-slate-900">
                    {patientProfile.allergies.join(', ') || 'Không có'}
                  </strong>
                  ), bệnh lý nền và các thuốc bạn đang dùng để phân loại mức độ
                  khẩn cấp và đưa ra hướng dẫn an toàn nhất.
                </p>
              </div>

              <div className="space-y-2">
                <span className="text-xs font-semibold text-slate-500 block">
                  Chọn tình huống mẫu để kiểm thử nhanh:
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {SYMPTOM_STARTERS.map((starter, idx) => (
                    <button
                      key={idx}
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
                      <span>Bạn</span>
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
                    <TriageIcon className={`h-4 w-4 shrink-0 ${cfg.iconColor}`} />
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
                  {/* Executive Summary */}
                  <div className="space-y-2">
                    <p className="text-sm font-semibold text-slate-900 leading-relaxed">
                      {triage.summary}
                    </p>
                    <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-line">
                      {triage.detailedExplanation}
                    </p>
                  </div>

                  {/* Personalized Profile Context Box */}
                  {triage.personalizedNotes && (
                    <div className="rounded-lg border border-teal-200 bg-teal-50/60 p-4 space-y-1">
                      <div className="text-xs font-bold text-teal-950">
                        Đối chiếu Cá nhân hóa từ Hồ sơ Sức khỏe của {patientProfile.fullName}
                      </div>
                      <p className="text-xs text-slate-800 leading-relaxed">
                        {triage.personalizedNotes}
                      </p>
                    </div>
                  )}

                  {/* 2-Column Clinical Breakdown: Possible Causes & Self Care */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {triage.possibleCauses.length > 0 && (
                      <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
                        <h4 className="text-xs font-bold text-slate-900 mb-2.5">
                          Nguyên nhân / Tình trạng có thể liên quan
                        </h4>
                        <ul className="space-y-1.5 text-xs text-slate-700 leading-relaxed">
                          {triage.possibleCauses.map((cause, i) => (
                            <li key={i} className="flex items-start gap-2">
                              <span className="font-mono-tabular font-semibold text-slate-500 shrink-0">
                                0{i + 1}.
                              </span>
                              <span>{cause}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {triage.selfCareSteps.length > 0 && (
                      <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
                        <h4 className="text-xs font-bold text-slate-900 mb-2.5">
                          Hướng dẫn chăm sóc & theo dõi an toàn
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
                  </div>

                  {/* Red Flags Warning Section */}
                  {triage.redFlags.length > 0 && (
                    <div className="rounded-lg border border-red-200 bg-red-50/60 p-4">
                      <div className="flex items-center gap-2 text-xs font-bold text-red-900 mb-2">
                        <AlertTriangle className="h-4 w-4 text-red-600 shrink-0" />
                        <span>
                          Dấu hiệu Cảnh báo Đỏ (Red Flags) — Cần đi khám cấp cứu ngay nếu xuất hiện:
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
                        Câu hỏi tiếp theo gợi ý cho bạn:
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {triage.followUpQuestions.map((q, i) => (
                          <button
                            key={i}
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
                Đang phân tích triệu chứng lâm sàng và đối chiếu tiền sử dị ứng trong hồ sơ...
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
                  onClick={() =>
                    sendMessage(lastFailedPayload.text, lastFailedPayload.img)
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
                    Đã đính kèm hình ảnh y tế
                  </p>
                  <p className="text-slate-500">
                    AI sẽ kết hợp phân tích hình ảnh và mô tả triệu chứng của bạn
                  </p>
                </div>
              </div>
              <button
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
                    sendMessage();
                  }
                }}
                placeholder="Mô tả triệu chứng, thời gian khởi phát, mức độ đau hoặc câu hỏi thuốc..."
                className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-teal-600 focus:outline-none"
              />
            </div>

            <button
              type="button"
              disabled={isLoading || (!inputText.trim() && !attachedImage)}
              onClick={() => sendMessage()}
              className="flex items-center gap-2 rounded-lg bg-teal-600 px-5 py-2.5 text-xs font-semibold text-white hover:bg-teal-700 transition-colors whitespace-nowrap shrink-0 disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
              <span>Phân tích</span>
            </button>
          </div>

          <p className="text-xs text-slate-500">
            Lưu ý y khoa: Thông tin từ Middies Health AI phục vụ mục đích sàng lọc và tham khảo sức khỏe, không thay thế chẩn đoán trực tiếp của bác sĩ.
          </p>
        </div>
      </div>

      {/* Right Column: Session History & Active Profile Context */}
      <div className="lg:col-span-4 space-y-5">
        {/* Active Patient Safety Context Card */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
          <div className="border-b border-slate-200 pb-3">
            <span className="text-xs font-medium text-slate-500">
              NGỮ CẢNH AN TOÀN Y KHOA ĐANG BẬT
            </span>
            <h3 className="text-sm font-bold text-slate-900 mt-0.5">
              Hồ sơ: {patientProfile.fullName}
            </h3>
            <p className="text-xs text-slate-500 font-mono-tabular mt-0.5">
              <span>Năm sinh {patientProfile.birthYear}</span>
              <span aria-hidden="true"> · </span>
              <span>Nhóm máu {patientProfile.bloodType}</span>
              <span aria-hidden="true"> · </span>
              <span>
                {patientProfile.heightCm}cm / {patientProfile.weightKg}kg
              </span>
            </p>
          </div>

          <div className="space-y-2.5 text-xs">
            <div>
              <span className="font-semibold text-red-700 block">
                Cảnh báo Dị ứng Tự động:
              </span>
              <p className="text-slate-700 mt-0.5">
                {patientProfile.allergies.length > 0
                  ? patientProfile.allergies.join(' · ')
                  : 'Chưa ghi nhận dị ứng'}
              </p>
            </div>

            <div>
              <span className="font-semibold text-slate-800 block">
                Bệnh lý nền đang theo dõi:
              </span>
              <p className="text-slate-600 mt-0.5">
                {patientProfile.chronicConditions.length > 0
                  ? patientProfile.chronicConditions.join(' · ')
                  : 'Không có'}
              </p>
            </div>

            <div>
              <span className="font-semibold text-slate-800 block">
                Thuốc đang dùng định kỳ ({patientProfile.medications.length}):
              </span>
              <p className="text-slate-600 mt-0.5">
                {patientProfile.medications.length > 0
                  ? patientProfile.medications.map((m) => m.name).join(' · ')
                  : 'Không có'}
              </p>
            </div>
          </div>
        </div>

        {/* Consultation Sessions List */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3.5">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <h3 className="text-sm font-bold text-slate-900">
              Lịch Sử Phiên Tư Vấn ({sessions.length})
            </h3>
            <button
              onClick={onCreateNewSession}
              className="text-xs font-semibold text-teal-700 hover:text-teal-800 whitespace-nowrap"
            >
              + Phiên mới
            </button>
          </div>

          <div className="space-y-2 max-h-80 overflow-y-auto">
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
                    onClick={() => onSelectSession(s.id)}
                    className="flex-1 text-left min-w-0"
                  >
                    <p className="text-xs font-semibold text-slate-900 truncate">
                      {s.title}
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5 font-mono-tabular">
                      <span>{s.messages.length} tin nhắn</span>
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
  );
};

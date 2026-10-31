import React, { useState, useEffect } from 'react';
import {
  Stethoscope,
  Database,
  FileSearch,
  Pill,
  UserCheck,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import {
  ActiveWorkspaceTab,
  ChatMessage,
  ChatSession,
  DocumentAnalysisResult,
  InferenceEngineMode,
  MedicationSlot,
  PatientProfile,
  TriageLevel,
} from './types/health';
import {
  DEFAULT_PATIENT_PROFILE,
  INITIAL_CHAT_SESSIONS,
  INITIAL_DOCUMENT_HISTORY,
  getTodayDateString,
} from './data/defaultHealthData';
import { SymptomChatView } from './components/SymptomChatView';
import { MeddiesResearchView } from './components/MeddiesResearchView';
import { DocumentScannerView } from './components/DocumentScannerView';
import { DrugInteractionView } from './components/DrugInteractionView';
import { HealthProfileView } from './components/HealthProfileView';
import { EmergencyGuideModal } from './components/EmergencyGuideModal';

const STORAGE_KEYS = {
  PROFILE: 'middies_health_profile_v1',
  SESSIONS: 'middies_chat_sessions_v2',
  DOCUMENTS: 'middies_doc_history_v1',
};

export function App() {
  const [activeTab, setActiveTab] = useState<ActiveWorkspaceTab>('chat');
  const [inferenceMode, setInferenceMode] =
    useState<InferenceEngineMode>('cloud_hybrid');
  const [pendingSamplePrompt, setPendingSamplePrompt] = useState<{
    prompt: string;
    title: string;
  } | null>(null);
  const [isEmergencyOpen, setIsEmergencyOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Persistent Local State
  const [patientProfile, setPatientProfile] = useState<PatientProfile>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEYS.PROFILE);
      if (saved) return JSON.parse(saved);
    } catch {
      // Fallback to default
    }
    return DEFAULT_PATIENT_PROFILE;
  });

  const [chatSessions, setChatSessions] = useState<ChatSession[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEYS.SESSIONS);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {
      // Fallback
    }
    return INITIAL_CHAT_SESSIONS;
  });

  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    return chatSessions[0]?.id || 'session-welcome';
  });

  const [docHistory, setDocHistory] = useState<DocumentAnalysisResult[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEYS.DOCUMENTS);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {
      // Fallback
    }
    return INITIAL_DOCUMENT_HISTORY;
  });

  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEYS.PROFILE,
        JSON.stringify(patientProfile)
      );
    } catch {
      // Ignore quota errors
    }
  }, [patientProfile]);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEYS.SESSIONS, JSON.stringify(chatSessions));
    } catch {
      // Ignore quota errors
    }
  }, [chatSessions]);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEYS.DOCUMENTS, JSON.stringify(docHistory));
    } catch {
      // Ignore quota errors
    }
  }, [docHistory]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((prev) => (prev === msg ? null : prev));
    }, 3500);
  };

  const handleCreateNewSession = () => {
    const newId = `session-${Date.now()}`;
    const newSession: ChatSession = {
      id: newId,
      title: 'Phiên tư vấn sức khỏe mới',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messages: [],
    };
    setChatSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newId);
    setActiveTab('chat');
  };

  const handleRunSampleInChat = (initialPrompt: string, sampleTitle: string) => {
    const newId = `session-${Date.now()}`;
    const newSession: ChatSession = {
      id: newId,
      title: sampleTitle.slice(0, 48),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messages: [],
    };
    setChatSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newId);
    setPendingSamplePrompt({ prompt: initialPrompt, title: sampleTitle });
    setActiveTab('chat');
    showToast(`Đang chạy thử kịch bản "${sampleTitle}" từ tập dữ liệu Meddies/meddies-consultant...`);
  };

  const handleDeleteSession = (id: string) => {
    setChatSessions((prev) => {
      const remaining = prev.filter((s) => s.id !== id);
      if (activeSessionId === id && remaining.length > 0) {
        setActiveSessionId(remaining[0].id);
      }
      return remaining;
    });
  };

  const handleUpdateSessionMessages = (
    sessionId: string,
    messages: ChatMessage[],
    newTitle?: string,
    lastTriage?: TriageLevel
  ) => {
    setChatSessions((prev) =>
      prev.map((s) =>
        s.id === sessionId
          ? {
              ...s,
              title: newTitle || s.title,
              updatedAt: new Date().toISOString(),
              lastTriageLevel: lastTriage || s.lastTriageLevel,
              messages,
            }
          : s
      )
    );
  };

  const handleAddMedicationFromScanner = (med: {
    name: string;
    dosage: string;
    frequency: string;
    slots: MedicationSlot[];
    instructions: string;
    purpose: string;
  }) => {
    const nextMed = {
      id: `med-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      name: med.name,
      dosage: med.dosage,
      frequency: med.frequency,
      slots: med.slots,
      instructions: med.instructions,
      purpose: med.purpose,
      takenSlotsToday: [] as MedicationSlot[],
      lastUpdatedDate: getTodayDateString(),
    };
    setPatientProfile((prev) => ({
      ...prev,
      medications: [...prev.medications, nextMed],
    }));
    showToast(`Đã thêm "${med.name}" vào Lịch nhắc uống thuốc hàng ngày.`);
  };

  const handleExportBackup = () => {
    const payload = {
      exportedAt: new Date().toISOString(),
      patientProfile,
      chatSessions,
      docHistory,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `middies-health-backup-${getTodayDateString()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Đã xuất tệp sao lưu hồ sơ sức khỏe thành công.');
  };

  const handleImportBackup = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(reader.result as string);
        if (parsed.patientProfile) setPatientProfile(parsed.patientProfile);
        if (Array.isArray(parsed.chatSessions))
          setChatSessions(parsed.chatSessions);
        if (Array.isArray(parsed.docHistory)) setDocHistory(parsed.docHistory);
        showToast('Đã khôi phục dữ liệu hồ sơ sức khỏe thành công.');
      } catch {
        showToast('Tệp sao lưu không hợp lệ.');
      }
    };
    reader.readAsText(file);
  };

  const handleResetDefault = () => {
    setPatientProfile(DEFAULT_PATIENT_PROFILE);
    setChatSessions(INITIAL_CHAT_SESSIONS);
    setDocHistory(INITIAL_DOCUMENT_HISTORY);
    setActiveSessionId(INITIAL_CHAT_SESSIONS[0].id);
    showToast('Đã khôi phục dữ liệu mẫu lâm sàng ban đầu.');
  };

  const totalDosesToday = patientProfile.medications.reduce(
    (acc, m) => acc + m.slots.length,
    0
  );
  const takenDosesToday = patientProfile.medications.reduce(
    (acc, m) => acc + m.takenSlotsToday.length,
    0
  );

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      {/* Strict 3-Zone Top Bar Contract */}
      <header className="sticky top-0 z-30 flex items-center justify-between gap-8 border-b border-slate-200 bg-white px-6 py-3.5">
        {/* Zone 1: Single text element wordmark */}
        <a
          href="#top"
          onClick={(e) => {
            e.preventDefault();
            setActiveTab('chat');
          }}
          className="font-display text-lg font-bold tracking-tight text-slate-900 whitespace-nowrap shrink-0"
        >
          Ứng Dụng AI Cho Bài Toán Y Tế · Meddies AI
        </a>

        {/* Zone 2: Concise single-line navigation links */}
        <nav className="hidden lg:flex items-center gap-6 text-sm font-medium text-slate-600">
          <a
            href="#chat"
            onClick={(e) => {
              e.preventDefault();
              setActiveTab('chat');
            }}
            className={`transition-colors whitespace-nowrap shrink-0 hover:text-slate-900 ${
              activeTab === 'chat'
                ? 'text-teal-700 font-semibold underline underline-offset-8'
                : ''
            }`}
          >
            Tư Vấn & Dự Đoán Bệnh
          </a>
          <a
            href="#meddies_research"
            onClick={(e) => {
              e.preventDefault();
              setActiveTab('meddies_research');
            }}
            className={`transition-colors whitespace-nowrap shrink-0 hover:text-slate-900 ${
              activeTab === 'meddies_research'
                ? 'text-teal-700 font-semibold underline underline-offset-8'
                : ''
            }`}
          >
            Mô Hình & Dataset Meddies
          </a>
          <a
            href="#scanner"
            onClick={(e) => {
              e.preventDefault();
              setActiveTab('scanner');
            }}
            className={`transition-colors whitespace-nowrap shrink-0 hover:text-slate-900 ${
              activeTab === 'scanner'
                ? 'text-teal-700 font-semibold underline underline-offset-8'
                : ''
            }`}
          >
            Đọc Đơn & Xét Nghiệm
          </a>
          <a
            href="#interactions"
            onClick={(e) => {
              e.preventDefault();
              setActiveTab('interactions');
            }}
            className={`transition-colors whitespace-nowrap shrink-0 hover:text-slate-900 ${
              activeTab === 'interactions'
                ? 'text-teal-700 font-semibold underline underline-offset-8'
                : ''
            }`}
          >
            Tương Tác Thuốc
          </a>
          <a
            href="#profile"
            onClick={(e) => {
              e.preventDefault();
              setActiveTab('profile');
            }}
            className={`transition-colors whitespace-nowrap shrink-0 hover:text-slate-900 ${
              activeTab === 'profile'
                ? 'text-teal-700 font-semibold underline underline-offset-8'
                : ''
            }`}
          >
            Hồ Sơ Sức Khỏe
          </a>
        </nav>

        {/* Zone 3: 1 primary action */}
        <div className="flex items-center shrink-0">
          <button
            type="button"
            onClick={() => setIsEmergencyOpen(true)}
            className="px-4 py-2 text-xs font-semibold text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors whitespace-nowrap shrink-0"
          >
            Cấp Cứu 115 & Thẻ Y Tế
          </button>
        </div>
      </header>

      {/* Main Clinical Workspace Container */}
      <div className="flex-1 mx-auto w-full max-w-[1440px] px-4 sm:px-6 py-6 grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        {/* Left Workspace Sidebar */}
        <aside className="xl:col-span-3 space-y-5">
          {/* Thesis Overview Summary Card */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2">
            <span className="text-[11px] font-bold text-teal-700 block">
              ĐỀ TÀI NGHIÊN CỨU & SẢN PHẨM
            </span>
            <h1 className="text-sm font-bold text-slate-900">
              Ứng dụng AI cho bài toán Y Tế
            </h1>
            <p className="text-xs text-slate-600 leading-relaxed">
              Hội thoại thu thập triệu chứng đa lượt, phân tích và dự đoán các
              bệnh có khả năng liên quan dựa trên dữ liệu{' '}
              <span className="font-mono-tabular font-semibold text-slate-800">
                Meddies/meddies-consultant
              </span>
              , cung cấp thông tin tham khảo và khuyến nghị cơ sở y tế.
            </p>
          </div>

          {/* Workspace Module Selector */}
          <div className="rounded-xl border border-slate-200 bg-white p-3 space-y-1">
            {[
              {
                id: 'chat' as ActiveWorkspaceTab,
                label: '01. Tư Vấn & Dự Đoán Bệnh Liên Quan',
                sub: 'Hỏi bổ sung đa lượt & Khuyến nghị y tế',
                icon: Stethoscope,
              },
              {
                id: 'meddies_research' as ActiveWorkspaceTab,
                label: '02. Mô Hình & Dataset Meddies',
                sub: 'Trình diễn dữ liệu & Thực nghiệm QLoRA',
                icon: Database,
              },
              {
                id: 'scanner' as ActiveWorkspaceTab,
                label: '03. Đọc Đơn Thuốc & Xét Nghiệm',
                sub: 'Bóc tách chỉ số qua ảnh OCR',
                icon: FileSearch,
              },
              {
                id: 'interactions' as ActiveWorkspaceTab,
                label: '04. Tra Cứu & Tương Tác Thuốc',
                sub: 'Tìm nhanh tên thuốc & Kiểm tra xung đột',
                icon: Pill,
              },
              {
                id: 'profile' as ActiveWorkspaceTab,
                label: '05. Hồ Sơ & Lịch Nhắc Thuốc',
                sub: `Hôm nay: ${takenDosesToday}/${totalDosesToday} liều đã uống`,
                icon: UserCheck,
              },
            ].map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-start gap-3 rounded-lg p-3 text-left transition-colors ${
                    isActive
                      ? 'bg-teal-600 text-white'
                      : 'text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  <Icon
                    className={`h-4 w-4 mt-0.5 shrink-0 ${
                      isActive ? 'text-white' : 'text-teal-600'
                    }`}
                  />
                  <div className="min-w-0">
                    <p className="text-xs font-bold truncate">{item.label}</p>
                    <p
                      className={`text-xs truncate mt-0.5 ${
                        isActive ? 'text-teal-100' : 'text-slate-500'
                      }`}
                    >
                      {item.sub}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Patient Quick Summary & Medication Adherence Card */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3.5">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
              <div>
                <span className="text-xs text-slate-500 block">
                  NGỮ CẢNH HỒ SƠ NGƯỜI DÙNG
                </span>
                <h2 className="text-sm font-bold text-slate-900">
                  {patientProfile.fullName}
                </h2>
              </div>
              <span className="font-mono-tabular text-xs font-bold text-teal-700">
                Nhóm máu {patientProfile.bloodType}
              </span>
            </div>

            <div className="text-xs text-slate-600 space-y-1.5">
              <p>
                <strong className="text-red-700">Dị ứng: </strong>
                {patientProfile.allergies.length > 0
                  ? patientProfile.allergies.join(' · ')
                  : 'Không có'}
              </p>
              <p>
                <strong className="text-slate-800">Bệnh nền: </strong>
                {patientProfile.chronicConditions.length > 0
                  ? patientProfile.chronicConditions.join(' · ')
                  : 'Không có'}
              </p>
            </div>

            <button
              type="button"
              onClick={() => setIsEmergencyOpen(true)}
              className="w-full flex items-center justify-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-800 hover:bg-red-100 transition-colors"
            >
              <ShieldAlert className="h-4 w-4 text-red-600 shrink-0" />
              <span>Xem Sơ Cứu Đột Quỵ & Phản Vệ</span>
            </button>
          </div>
        </aside>

        {/* Main Active Viewport (9 columns on XL) */}
        <main className="xl:col-span-9 min-w-0">
          {activeTab === 'chat' && (
            <SymptomChatView
              sessions={chatSessions}
              activeSessionId={activeSessionId}
              onSelectSession={setActiveSessionId}
              onCreateNewSession={handleCreateNewSession}
              onDeleteSession={handleDeleteSession}
              onUpdateSessionMessages={handleUpdateSessionMessages}
              patientProfile={patientProfile}
              onOpenEmergencyModal={() => setIsEmergencyOpen(true)}
              inferenceMode={inferenceMode}
              onChangeInferenceMode={(mode) => {
                setInferenceMode(mode);
                showToast(
                  mode === 'cloud_hybrid'
                    ? 'Đã chuyển sang Chế độ 1: Suy luận trực tuyến kèm RAG Meddies/meddies-consultant.'
                    : 'Đã chuyển sang Chế độ 2: Kết nối FastAPI Qwen Fine-Tuned (:8000) kèm dự phòng tự động.'
                );
              }}
              onOpenMeddiesResearchTab={() => setActiveTab('meddies_research')}
              pendingSamplePrompt={pendingSamplePrompt}
              onClearPendingSamplePrompt={() => setPendingSamplePrompt(null)}
            />
          )}

          {activeTab === 'meddies_research' && (
            <MeddiesResearchView
              inferenceMode={inferenceMode}
              onChangeInferenceMode={(mode) => {
                setInferenceMode(mode);
                showToast(
                  mode === 'cloud_hybrid'
                    ? 'Đã chuyển sang Chế độ 1: Suy luận trực tuyến kèm RAG Meddies/meddies-consultant.'
                    : 'Đã chuyển sang Chế độ 2: Kết nối FastAPI Qwen Fine-Tuned (:8000) kèm dự phòng tự động.'
                );
              }}
              onRunSampleInChat={handleRunSampleInChat}
            />
          )}

          {activeTab === 'scanner' && (
            <DocumentScannerView
              history={docHistory}
              onSaveAnalysis={(res) =>
                setDocHistory((prev) => [res, ...prev])
              }
              patientProfile={patientProfile}
              onAddMedicationToProfile={handleAddMedicationFromScanner}
            />
          )}

          {activeTab === 'interactions' && (
            <DrugInteractionView patientProfile={patientProfile} />
          )}

          {activeTab === 'profile' && (
            <HealthProfileView
              profile={patientProfile}
              onUpdateProfile={setPatientProfile}
              onExportBackup={handleExportBackup}
              onImportBackup={handleImportBackup}
              onResetDefault={handleResetDefault}
            />
          )}
        </main>
      </div>

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-5 right-5 z-40 flex items-center gap-2.5 rounded-xl border border-teal-200 bg-slate-900 px-4 py-3 text-xs font-medium text-white shadow-lg">
          <CheckCircle2 className="h-4 w-4 text-teal-400 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Emergency First Aid & Personal Medical ID Modal */}
      <EmergencyGuideModal
        isOpen={isEmergencyOpen}
        onClose={() => setIsEmergencyOpen(false)}
        profile={patientProfile}
      />

      {/* Clean Clinical Footer */}
      <footer className="border-t border-slate-200 bg-white px-6 py-4 mt-8">
        <div className="mx-auto max-w-[1440px] flex flex-wrap items-center justify-between gap-4 text-xs text-slate-500">
          <p>
            Đề tài: Ứng dụng AI cho bài toán Y Tế · Dữ liệu hội thoại y tế tiếng Việt Meddies/meddies-consultant (revision 05428709a).
          </p>
          <p className="flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 shrink-0" />
            <span>
              Hệ thống hướng tới vai trò hỗ trợ sàng lọc và cung cấp thông tin ban đầu, không thay thế chẩn đoán của bác sĩ.
            </span>
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;

import React, { useState, useEffect } from 'react';
import {
  Stethoscope,
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
import { DocumentScannerView } from './components/DocumentScannerView';
import { DrugInteractionView } from './components/DrugInteractionView';
import { HealthProfileView } from './components/HealthProfileView';
import { EmergencyGuideModal } from './components/EmergencyGuideModal';

const STORAGE_KEYS = {
  PROFILE: 'middies_health_profile_v1',
  SESSIONS: 'middies_chat_sessions_v1',
  DOCUMENTS: 'middies_doc_history_v1',
};

export function App() {
  const [activeTab, setActiveTab] = useState<ActiveWorkspaceTab>('chat');
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
      localStorage.setItem(STORAGE_KEYS.PROFILE, JSON.stringify(patientProfile));
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
          Middies Health AI
        </a>

        {/* Zone 2: 4 concise single-line navigation links */}
        <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-slate-600">
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
            Tư Vấn Triệu Chứng
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
            Hồ Sơ & Lịch Thuốc
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
        {/* Left Workspace Sidebar (260px on desktop) */}
        <aside className="xl:col-span-3 space-y-5">
          {/* Workspace Module Selector */}
          <div className="rounded-xl border border-slate-200 bg-white p-3 space-y-1">
            {[
              {
                id: 'chat' as ActiveWorkspaceTab,
                label: 'Trợ Lý Tư Vấn & Phân Loại',
                sub: 'Hỏi đáp & Sàng lọc mức khẩn cấp',
                icon: Stethoscope,
              },
              {
                id: 'scanner' as ActiveWorkspaceTab,
                label: 'Đọc Đơn Thuốc & Xét Nghiệm',
                sub: 'Bóc tách chỉ số qua ảnh OCR',
                icon: FileSearch,
              },
              {
                id: 'interactions' as ActiveWorkspaceTab,
                label: 'Tra Cứu & Tương Tác Thuốc',
                sub: 'Kiểm tra xung đột đa hoạt chất',
                icon: Pill,
              },
              {
                id: 'profile' as ActiveWorkspaceTab,
                label: 'Hồ Sơ & Lịch Nhắc Thuốc',
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
                  BỆNH NHÂN ĐANG THEO DÕI
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

            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-800">
                  Lịch uống thuốc hôm nay
                </span>
                <span className="font-mono-tabular font-bold text-teal-700">
                  {takenDosesToday}/{totalDosesToday} cử
                </span>
              </div>
              <button
                type="button"
                onClick={() => setActiveTab('profile')}
                className="w-full rounded-md border border-slate-300 bg-white py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-100 transition-colors"
              >
                Mở Bảng Đánh Dấu Uống Thuốc
              </button>
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
            Middies Health AI · Hệ thống trợ lý thông tin y khoa & quản lý sức khỏe cá nhân lưu trữ cục bộ bảo mật.
          </p>
          <p className="flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 shrink-0" />
            <span>
              Mọi nội dung tư vấn mang tính chất tham khảo y tế, không thay thế việc thăm khám và kê đơn trực tiếp của bác sĩ.
            </span>
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;

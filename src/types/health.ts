import { DialogueStateAnalysis } from '../services/dialogueEngine';

export type TriageLevel = 'NORMAL' | 'MONITOR' | 'SOON' | 'EMERGENCY';

export type MedicationSlot = 'Sáng' | 'Trưa' | 'Chiều' | 'Tối';

export interface VitalLog {
  id: string;
  recordedAt: string;
  systolic: number;
  diastolic: number;
  heartRate: number;
  bloodSugar?: number;
  temperatureC?: number;
  note?: string;
}

export interface MedicationReminder {
  id: string;
  name: string;
  dosage: string;
  frequency: string;
  slots: MedicationSlot[];
  instructions: string;
  purpose?: string;
  takenSlotsToday: MedicationSlot[];
  lastUpdatedDate: string;
}

export interface PatientProfile {
  fullName: string;
  birthYear: number;
  gender: 'Nam' | 'Nữ' | 'Khác';
  bloodType: 'O+' | 'O-' | 'A+' | 'A-' | 'B+' | 'B-' | 'AB+' | 'AB-' | 'Chưa rõ';
  heightCm: number;
  weightKg: number;
  allergies: string[];
  chronicConditions: string[];
  emergencyContactName: string;
  emergencyContactPhone: string;
  medications: MedicationReminder[];
  vitalLogs: VitalLog[];
}

export type InferenceEngineMode = 'cloud_hybrid' | 'qwen_local';

export interface TriageResponseData {
  triageLevel: TriageLevel;
  triageTitle: string;
  summary: string;
  detailedExplanation: string;
  possibleCauses: string[];
  selfCareSteps: string[];
  redFlags: string[];
  personalizedNotes: string;
  followUpQuestions: string[];
  dialogueState?: DialogueStateAnalysis;
  activeEngine?: string;
  fallbackNotice?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  imagePreviewUrl?: string;
  triageData?: TriageResponseData;
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  lastTriageLevel?: TriageLevel;
  messages: ChatMessage[];
}

export interface LabMetricItem {
  name: string;
  value: string;
  unit: string;
  referenceRange: string;
  status: 'NORMAL' | 'HIGH' | 'LOW' | 'INFO';
  explanation: string;
}

export interface ExtractedMedicationItem {
  name: string;
  dosage: string;
  frequency: string;
  timing: MedicationSlot[];
  instructions: string;
  purpose: string;
  allergyWarning: string;
}

export interface DocumentAnalysisResult {
  id: string;
  analyzedAt: string;
  detectedType: 'PRESCRIPTION' | 'LAB_RESULT' | 'MEDICAL_NOTE';
  title: string;
  overallSummary: string;
  triageStatus: 'NORMAL' | 'ATTENTION' | 'CRITICAL';
  metrics: LabMetricItem[];
  extractedMedications: ExtractedMedicationItem[];
  recommendations: string[];
  questionsForDoctor: string[];
  imagePreviewUrl?: string;
}

export interface DrugInteractionResult {
  overallSafety: 'SAFE' | 'CAUTION' | 'CONTRAINDICATED';
  safetyHeadline: string;
  summary: string;
  pairInteractions: {
    pair: string;
    severity: 'NONE' | 'MILD' | 'MODERATE' | 'SEVERE';
    mechanism: string;
    recommendation: string;
  }[];
  profileAlerts: string[];
  medicationProfiles: {
    name: string;
    activeIngredient: string;
    mainUse: string;
    bestTiming: string;
    commonSideEffects: string[];
    foodInteractions: string;
  }[];
}

export type ActiveWorkspaceTab =
  | 'chat'
  | 'meddies_research'
  | 'scanner'
  | 'interactions'
  | 'profile';


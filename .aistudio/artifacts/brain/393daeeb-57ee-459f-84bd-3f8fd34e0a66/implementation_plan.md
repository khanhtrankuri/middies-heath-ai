# Middies Health AI — Hệ Thống Trợ Lý Y Tế & Chăm Sóc Sức Khỏe Cá Nhân Toàn Diện

Đánh giá hiện trạng kho mã nguồn (hiện mới chỉ khởi tạo tệp `README.md` trống) và thiết lập kiến trúc hoàn chỉnh từ đầu cho **Middies Health AI** — nền tảng chatbot y tế đa phương thức, phân loại mức độ khẩn cấp lâm sàng (Triage), giải thích đơn thuốc/kết quả xét nghiệm qua hình ảnh, kiểm tra tương tác thuốc và quản lý hồ sơ sức khỏe cá nhân ổn định, bảo mật.

---

## Đánh Giá Hiện Trạng Dự Án (Project Assessment)

> [!NOTE]
> Qua kiểm tra toàn bộ cây thư mục gốc của dự án, kho lưu trữ hiện chỉ có duy nhất tệp `README.md` (`# middies-heath-ai`) và chưa có khung mã nguồn Frontend/Backend, cấu hình gói (`package.json`), hay kết nối AI. Đây là cơ hội lý tưởng để thiết kế một kiến trúc Full-Stack chuẩn mực ngay từ đầu, tránh nợ kỹ thuật và đảm bảo tính ổn định cao nhất.

### User Review & Các Quyết Định Cốt Lõi Đã Xác Nhận

> [!IMPORTANT]
> Dưới đây là các quyết định sản phẩm đã được xác nhận từ câu trả lời của bạn để định hình kiến trúc hệ thống:

- **Đối tượng phục vụ chính**: Bệnh nhân và người dùng cá nhân tra cứu sức khỏe, cần ngôn ngữ giải thích dễ hiểu, thấu cảm, chính xác và có cảnh báo y khoa rõ ràng.
- **Bộ 4 tính năng trọng tâm**:
  1. **Trợ lý Hội thoại & Phân tích Triệu chứng (Symptom Triage)**: Hỏi đáp y tế thông minh kết hợp tự động phân loại mức độ khẩn cấp (Cấp cứu / Cần khám sớm / Theo dõi tại nhà) kèm hướng dẫn hành động.
  2. **Đọc & Giải thích Đơn thuốc / Xét nghiệm qua Ảnh (Multimodal Medical OCR)**: Tải ảnh chụp đơn thuốc, phiếu xét nghiệm máu/nước tiểu để AI trích xuất chỉ số, đối chiếu ngưỡng bình thường và giải thích ý nghĩa bằng tiếng Việt dễ hiểu.
  3. **Tra cứu Thuốc & Kiểm tra Tương tác Thuốc (Drug Interaction Checker)**: Kiểm tra độ an toàn khi dùng chung nhiều loại thuốc, cảnh báo xung đột hoạt chất, tác dụng phụ và lưu ý dùng thuốc.
  4. **Hồ sơ Sức khỏe Cá nhân & Lịch Nhắc Uống Thuốc (Personal Health Profile & Medication Reminders)**: Lưu trữ thông tin cơ bản (nhóm máu, dị ứng, bệnh nền, chỉ số sinh tồn) và lịch nhắc uống thuốc hàng ngày; tự động đưa ngữ cảnh dị ứng/bệnh nền vào phiên tư vấn để cá nhân hóa câu trả lời.
- **Chiến lược Lưu trữ & Bảo mật**: Lưu trữ cục bộ hoàn toàn trên trình duyệt (`localStorage` có cấu trúc kết hợp tính năng Xuất/Nhập sao lưu tệp JSON), giúp tốc độ phản hồi tức thì, không phụ thuộc kết nối cơ sở dữ liệu bên ngoài và bảo vệ tuyệt đối quyền riêng tư y tế của người dùng.

---

## 1. Tổng Quan & Giá Trị Cốt Lõi (Overview & Core Concept)

- **Chức năng chính**: Middies Health AI hoạt động như một trợ lý y tế gia đình trực tuyến 24/7. Người dùng có thể trò chuyện trực tiếp về triệu chứng đang gặp phải, đính kèm hình ảnh phiếu xét nghiệm hoặc toa thuốc để được giải nghĩa chi tiết, kiểm tra chéo các loại thuốc đang uống và theo dõi lịch dùng thuốc gắn liền với hồ sơ bệnh sử cá nhân.
- **Đối tượng người dùng**: Người bệnh, người chăm sóc người thân trong gia đình, và cá nhân quan tâm đến theo dõi sức khỏe chủ động.
- **Giá trị khác biệt**:
  - **Cá nhân hóa an toàn**: Mọi tư vấn của AI đều tự động tham chiếu đến **Dị ứng**, **Bệnh lý nền** và **Thuốc đang sử dụng** trong Hồ sơ Sức khỏe của người dùng để ngăn ngừa rủi ro khuyến nghị sai lệch.
  - **Phân tầng khẩn cấp minh bạch**: Không trả lời chung chung; mỗi phản hồi triệu chứng đều đi kèm cấu trúc đánh giá mức độ khẩn cấp rõ ràng và cảnh báo các dấu hiệu nguy hiểm ("Red Flags") cần gọi cấp cứu 115 ngay.

---

## 2. Trải Nghiệm Người Dùng & Thiết Kế Giao Diện (UX & Visual Design)

- **Luồng trải nghiệm chính (Key User Flows)**:
  1. **Luồng Tư vấn & Phân loại Triệu chứng**: Người dùng chọn triệu chứng gợi ý nhanh hoặc nhập mô tả (có thể đính kèm ảnh) $\rightarrow$ Hệ thống gửi kèm ngữ cảnh Hồ sơ Sức khỏe (dị ứng, tuổi, bệnh nền) lên máy chủ AI $\rightarrow$ Trả về câu trả lời có cấu trúc gồm: *Đánh giá sơ bộ*, *Mức độ khẩn cấp (Triage Level)*, *Các câu hỏi làm rõ*, *Hướng dẫn chăm sóc tại nhà* và *Khi nào cần gặp bác sĩ ngay*.
  2. **Luồng Phân tích Đơn thuốc / Xét nghiệm qua Ảnh**: Người dùng tải lên ảnh chụp đơn thuốc hoặc bảng xét nghiệm $\rightarrow$ AI trích xuất thành bảng dữ liệu có cấu trúc (Tên chỉ số / Tên thuốc, Giá trị/Liều dùng, Trạng thái Bình thường/Cao/Thấp, Giải thích chi tiết) $\rightarrow$ Cho phép lưu trực tiếp thuốc từ đơn vào Lịch nhắc uống thuốc chỉ với 1 cú nhấp.
  3. **Luồng Kiểm tra Tương tác Thuốc**: Người dùng nhập từ 2 loại thuốc trở lên (hoặc chọn nhanh từ danh sách thuốc đang uống trong hồ sơ) $\rightarrow$ Hệ thống phân tích cơ chế tương tác giữa các hoạt chất, mức độ nghiêm trọng (An toàn / Thận trọng / Nghiêm trọng) và khuyến nghị cách dùng.
  4. **Luồng Quản lý Hồ sơ & Nhắc Thuốc**: Cập nhật thông tin chiều cao, cân nặng, BMI tự động, nhóm máu, tiền sử dị ứng, bệnh mãn tính; theo dõi danh sách cử uống thuốc trong ngày (Sáng / Trưa / Chiều / Tối) với thao tác đánh dấu đã uống trực quan.

- **Định hướng Thẩm mỹ & Giao diện (Visual Identity & Theme)**:
  - *Phong cách chủ đạo*: **Clinical Precision & Warm Empathy** — Sự kết hợp giữa độ chuẩn xác, sạch sẽ của hệ thống y khoa hiện đại (SaaS/Clinical Dashboard) và sự ấm áp, an tâm dành cho bệnh nhân.
  - *Bảng màu (60-30-10 Color Discipline)*:
    - **60% Nền trung tính sáng sạch**: Trắng sứ y tế và xám lạnh dịu mắt (`#F8FAFC` / `bg-slate-50` và `#FFFFFF` / `bg-white`), giúp đọc văn bản dài và bảng chỉ số xét nghiệm không bị mỏi mắt.
    - **30% Bề mặt cấu trúc & Viền mảnh**: Xám đá phiến (`#E2E8F0` / `border-slate-200`, văn bản `#0F172A` / `text-slate-900` và `#475569` / `text-slate-600`).
    - **10% Điểm nhấn & Trạng thái Y khoa (Semantic Triage Colors)**:
      - Xanh Ngọc Y Tế (`#0D9488` / `teal-600`): Màu hành động chính, tạo cảm giác tin cậy và bình tĩnh.
      - Xanh Lá An Toàn (`#16A34A` / `emerald-600`): Chỉ số bình thường / Tự theo dõi tại nhà.
      - Vàng Hổ Phách Cảnh Báo (`#D97706` / `amber-600`): Chỉ số cần lưu ý / Nên đặt lịch khám chuyên khoa.
      - Đỏ Lâm Sàng Khẩn Cấp (`#DC2626` / `red-600`): Dấu hiệu nguy hiểm / Tương tác thuốc nghiêm trọng / Cần cấp cứu y tế (115).
  - *Hệ thống Phông chữ (Typography)*:
    - Tiêu đề & Điều hướng: `Plus Jakarta Sans` — hiện đại, rõ ràng, tạo cảm giác chuyên nghiệp.
    - Nội dung tư vấn & Y văn: `Public Sans` hoặc `DM Sans` — tối ưu độ dễ đọc cho tiếng Việt ở kích thước 14px–16px.
    - Số liệu sinh tồn, Liều lượng & Chỉ số xét nghiệm: `JetBrains Mono` (`tabular-nums`) — đảm bảo các con số mg, ml, mmol/L, huyết áp, nhịp tim thẳng hàng tuyệt đối.
  - *Bố cục Không gian (Workspace Layout)*:
    - Khung nhìn Desktop chuẩn 1440px với **Thanh điều hướng bên trái (Sidebar 260px)** để chuyển đổi mượt mà giữa 4 phân khu (*Trợ lý Tư vấn AI*, *Phân tích Đơn thuốc & Xét nghiệm*, *Tra cứu & Tương tác Thuốc*, *Hồ sơ Sức khỏe & Lịch Thuốc*) và quản lý danh sách phiên hội thoại.
    - **Thanh Top Bar chuẩn 3 vùng**: Tên thương hiệu & Đường dẫn phân khu bên trái — Các liên kết chuyển nhanh ở giữa — Nút hành động khẩn cấp (Hướng dẫn Sơ cứu / Gọi 115 nhanh & Xuất Hồ sơ) bên phải.

---

## 3. Các Quyết Định Kỹ Thuật & Đánh Đổi (Key Product Decisions & Trade-Offs)

- **Quyết định 1: Kiến trúc Proxy Máy chủ Bảo mật cho Gemini API (`Express + Vite Full-Stack`)**
  - *Cách tiếp cận*: Toàn bộ lệnh gọi mô hình AI (`@google/genai`) được thực thi tại tầng máy chủ (`server.ts`) thông qua các API nội bộ (`/api/health/*`). Trình duyệt chỉ gửi yêu cầu và nhận kết quả JSON/Stream.
  - *Lý do*: Bảo vệ tuyệt đối khóa API, kiểm soát chặt chẽ System Prompt y khoa (Medical Safety Guardrails), chuẩn hóa định dạng đầu ra (`responseSchema`) và xử lý lỗi tập trung ổn định.
- **Quyết định 2: Sử dụng Đầu ra Có Cấu trúc (`Structured JSON Schema`) Kết hợp Markdown Y khoa**
  - *Cách tiếp cận*: Thay vì chỉ trả về đoạn văn bản tự do dễ gây bỏ sót thông tin quan trọng, các API phân tích triệu chứng, đọc ảnh xét nghiệm và kiểm tra tương tác thuốc sử dụng `responseSchema` của `gemini-3.8-flash` để luôn trả về dữ liệu phân tách rõ: Mức độ khẩn cấp (`triageLevel`), Dấu hiệu cờ đỏ (`redFlags`), Bảng chỉ số (`metrics`), và Lời khuyên chi tiết.
  - *Lý do*: Giúp giao diện hiển thị trực quan các hộp cảnh báo mức độ khẩn cấp, bảng đối chiếu chỉ số xét nghiệm và nút thêm thuốc tự động mà không bao giờ bị lỗi định dạng.
- **Quyết định 3: Tiêm Ngữ cảnh Hồ sơ Sức khỏe Tự động (Context-Aware Medical Prompting)**
  - *Cách tiếp cận*: Mỗi khi người dùng đặt câu hỏi hoặc kiểm tra thuốc, hệ thống tự động đính kèm tóm tắt Hồ sơ Sức khỏe cục bộ (tuổi, giới tính, dị ứng thuốc/thực phẩm, bệnh nền, thuốc đang dùng) vào yêu cầu gửi lên AI.
  - *Lý do*: Ngăn chặn việc AI gợi ý hoạt chất mà người dùng bị dị ứng hoặc chống chỉ định với bệnh lý nền (ví dụ: đau dạ dày, suy thận, mang thai).

---

## 4. Kiến Trúc Hệ Thống & Luồng Dữ Liệu (Technical Architecture & Data Strategy)

### Sơ đồ Kiến trúc Tổng thể

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        TRÌNH DUYỆT NGƯỜI DÙNG (React + TypeScript)               │
│                                                                                  │
│  ┌──────────────────────┐   ┌─────────────────────────────────────────────────┐  │
│  │ Thanh Điều Hướng Bên │   │ Khu Vực Làm Việc Chính (Main Viewport)          │  │
│  │ (Sidebar Navigation) │   │                                                 │  │
│  │                      │   │  1. Trợ Lý Tư Vấn & Phân Loại Triệu Chứng       │  │
│  │ • Phiên trò chuyện   │   │     (Chat đa phương thức + Triage Cảnh báo)     │  │
│  │ • 4 Phân khu y tế    │   │  2. Phân Tích Đơn Thuốc & Xét Nghiệm (OCR)      │  │
│  │ • Tóm tắt Hồ sơ      │   │     (Tải ảnh -> Bảng chỉ số -> Lưu lịch thuốc)  │  │
│  │   & Nhắc thuốc hôm   │   │  3. Tra Cứu Thuốc & Kiểm Tra Tương Tác          │  │
│  │   nay                │   │     (Đối chiếu đa hoạt chất & cảnh báo xung đột)│  │
│  │ • Cẩm nang Cấp cứu   │   │  4. Hồ Sơ Sức Khỏe & Lịch Nhắc Uống Thuốc       │  │
│  │   115 & Sao lưu JSON │   │     (Chỉ số sinh tồn, dị ứng, theo dõi cử thuốc)│  │
│  └──────────┬───────────┘   └────────────────────────┬────────────────────────┘  │
│             │                                        │                           │
│             ▼                                        ▼                           │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │         Bộ Quản Lý Trạng Thái & Lưu Trữ Cục Bộ (Local Health Store)        │  │
│  │  • HealthProfile (Tuổi, Nhóm máu, BMI, Dị ứng, Bệnh nền, Chỉ số sinh tồn)  │  │
│  │  • MedicationSchedule (Danh sách thuốc, liều lượng, giờ uống, trạng thái)  │  │
│  │  • ChatSessions & MedicalLabRecords (Lịch sử tư vấn & kết quả phân tích)   │  │
│  └──────────────────────────────────────┬─────────────────────────────────────┘  │
└─────────────────────────────────────────┼────────────────────────────────────────┘
                                          │ HTTP POST (/api/health/*)
                                          │ + Ngữ cảnh Hồ sơ Sức khỏe & Hình ảnh Base64
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                     MÁY CHỦ ỨNG DỤNG (Express Server - Port 3000)                │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                Tầng Điều Phối & Bảo Toàn Y Khoa (API Routes)               │  │
│  │  • POST /api/health/chat       : Tư vấn triệu chứng + Đánh giá Triage      │  │
│  │  • POST /api/health/analyze-doc: Đọc ảnh đơn thuốc / phiếu xét nghiệm      │  │
│  │  • POST /api/health/interactions: Phân tích tương tác thuốc & chống chỉ định│  │
│  └──────────────────────────────────────┬─────────────────────────────────────┘  │
│                                         │ @google/genai SDK (gemini-3.8-flash)   │
│                                         ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │         Google Gemini AI + Hệ Thống Quy Tắc An Toàn Y Khoa (Guardrails)    │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Mô hình Dữ liệu Cục bộ (`LocalStorage` Schema)

1. **`PatientProfile` (Hồ sơ Sức khỏe Cá nhân)**:
   - Thông tin cơ bản: Họ tên, Năm sinh, Giới tính, Nhóm máu, Chiều cao (cm), Cân nặng (kg).
   - Danh sách cảnh báo y khoa: `allergies` (Dị ứng thuốc/thức ăn), `chronicConditions` (Bệnh lý nền như Cao huyết áp, Tiểu đường, Đau dạ dày), `emergencyContact` (Số điện thoại người thân).
   - Nhật ký sinh tồn (`vitalLogs`): Huyết áp tâm thu/tâm trương, Nhịp tim, Đường huyết, Nhiệt độ cơ thể theo thời gian.
2. **`MedicationItem` (Lịch Nhắc Uống Thuốc)**:
   - Tên thuốc, Hàm lượng, Liều dùng, Thời điểm uống (`Sáng`, `Trưa`, `Chiều`, `Tối`), Ghi chú (Trước/Sau ăn), và Danh sách đánh dấu hoàn thành theo ngày (`takenDates`).
3. **`ChatSession` & `ChatMessage` (Phiên Trò chuyện Y tế)**:
   - Lưu lịch sử các cuộc trò chuyện độc lập, cho phép tạo phiên mới, đổi tên, xóa phiên hoặc tìm kiếm lại tư vấn cũ. Mỗi tin nhắn của AI lưu kèm metadata phân loại khẩn cấp (`LOW` | `MEDIUM` | `HIGH` | `EMERGENCY`), các dấu hiệu cần lưu ý và câu hỏi gợi ý tiếp theo.
4. **`LabAndPrescriptionRecord` (Hồ sơ Phân tích Ảnh Y tế)**:
   - Lưu trữ kết quả đọc đơn thuốc hoặc phiếu xét nghiệm máu/sinh hóa gồm: Loại tài liệu, Tóm tắt tổng quan, Bảng danh sách chỉ số/thuốc trích xuất được, và Khuyến nghị theo dõi.

### Ánh xạ Tương tác & Xử lý Trạng thái (Interactive Component & State Mapping)

- **Bộ khung An toàn & Tuyên bố Miễn trừ Y khoa (Medical Disclaimer & Emergency Modal)**:
  - Luôn hiển thị thông báo rõ ràng rằng AI hỗ trợ cung cấp thông tin tham khảo, không thay thế chẩn đoán trực tiếp của bác sĩ.
  - Khi AI phát hiện triệu chứng thuộc nhóm `EMERGENCY` (như đau thắt ngực, khó thở cấp, dấu hiệu đột quỵ FAST, phản vệ), giao diện lập tức kích hoạt khung cảnh báo Đỏ Lâm Sàng nổi bật kèm hướng dẫn sơ cứu tại chỗ và nút gọi khẩn cấp 115.
- **Trình tải ảnh Đơn thuốc / Xét nghiệm Đa năng**:
  - Hỗ trợ kéo thả ảnh, chọn tệp từ thiết bị hoặc chọn nhanh **Mẫu Đơn thuốc / Phiếu xét nghiệm mẫu có sẵn** để người dùng có thể trải nghiệm và kiểm thử tính năng ngay lập tức.
  - Sau khi AI bóc tách danh sách thuốc từ ảnh chụp đơn thuốc, hiển thị nút **"Thêm vào Lịch nhắc thuốc"** ngay trên từng dòng thuốc để đồng bộ tự động sang tab Hồ sơ & Lịch thuốc.
- **Cơ chế Chịu lỗi & Ổn định Hệ thống (Resilience & Error Recovery)**:
  - Kiểm tra kích thước và định dạng ảnh trước khi gửi; tự động nén ảnh lớn trên trình duyệt (`canvas` resize) để đảm bảo tốc độ gửi API nhanh và không vượt giới hạn tải trọng.
  - Trạng thái chờ (Skeleton/Loading) hiển thị rõ từng bước xử lý của AI; nếu kết nối mạng gián đoạn, giữ nguyên nội dung người dùng đã nhập kèm nút **"Thử gửi lại"** mà không làm mất dữ liệu.
  - Hỗ trợ **Xuất hồ sơ ra tệp `.json` (Backup)** và **Khôi phục từ tệp `.json` (Restore)** cũng như **In / Xuất Báo cáo Tóm tắt Sức khỏe** để người dùng mang theo khi đi khám bác sĩ.

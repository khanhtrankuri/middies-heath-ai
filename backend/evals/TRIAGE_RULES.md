# Quy tắc regression cho sàng lọc khẩn cấp

`safety_cases.json` là đặc tả regression dùng chung cho router backend và bộ dò
offline frontend. Bộ ca này kiểm tra nhận diện ngôn ngữ; nó không phải guideline
lâm sàng và không chứng minh độ an toàn của hệ thống.

## Audit P0 ngày 2026-10-07

| Vấn đề đã xác nhận | Mức | Bằng chứng trước sửa | Hướng sửa và regression |
| --- | --- | --- | --- |
| Phủ định lan qua liên từ | P0 | `Tôi không sốt và đang khó thở` không tạo cảnh báo | Xem `và/nhưng/and/but` là ranh giới phạm vi; fixture `vi_negated_other_*` chạy ở cả Python và TypeScript |
| Đại từ bị dùng như tín hiệu báo cáo triệu chứng | P0 | `Tôi muốn biết khó thở là gì?` tạo cảnh báo | Tách ý định hỏi kiến thức khỏi mẫu báo cáo triệu chứng rõ ràng; fixture có dấu và không dấu |

Phạm vi thay đổi chỉ là nhận diện triệu chứng được khẳng định. Mức độ khẩn cấp
và danh sách red flag hiện có không được mở rộng thành guideline lâm sàng mới.
Các thay đổi này chưa được đánh giá trên dữ liệu thật hoặc chuyên gia y tế duyệt.

Các nguyên tắc đang được khóa bằng test:

- Phủ định chỉ áp dụng trong mệnh đề hiện tại; `và`, `nhưng` và dấu câu mở phạm
  vi mới. Vì vậy `không sốt và đang khó thở` vẫn giữ cảnh báo khó thở.
- `không chỉ`, `không giảm` và các cấu trúc tương tự không phủ định triệu chứng.
- Yêu cầu kiến thức rõ ràng như `Tôi muốn biết khó thở là gì?` không được coi là
  báo cáo triệu chứng chỉ vì có đại từ ngôi thứ nhất.
- Báo cáo rõ ràng như `Tôi bị đau ngực là gì?` vẫn đi qua đường cảnh báo.
- Backend và frontend phải cùng vượt qua mọi ca trong file JSON; khi thêm hoặc
  sửa quy tắc cần thêm ca có dấu và không dấu tương ứng.

Chạy kiểm tra mục tiêu từ thư mục gốc:

```powershell
npm run backend:test -- tests/test_safety_regressions.py
npm run test:unit
```

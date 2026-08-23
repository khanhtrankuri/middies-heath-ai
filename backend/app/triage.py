import re
import unicodedata

from .models import Possibility, TriageRequest, TriageResponse

DISCLAIMER = (
    "Thông tin này chỉ có tính tham khảo, không phải chẩn đoán y khoa và không "
    "thay thế việc thăm khám của bác sĩ."
)

RED_FLAGS: dict[str, tuple[str, ...]] = {
    "khó thở": ("kho tho", "không thở được", "khong tho duoc"),
    "đau ngực": ("dau nguc", "tức ngực", "tuc nguc"),
    "ngất": ("ngat", "bất tỉnh", "bat tinh"),
    "co giật": ("co giat",),
    "yếu hoặc liệt": ("yeu liet", "liệt", "liet"),
    "méo miệng": ("meo mieng",),
    "chảy máu nhiều": ("chay mau nhieu", "máu không cầm", "mau khong cam"),
}


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
    without_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_marks).strip()


def find_red_flags(text: str) -> list[str]:
    folded = _fold(text)
    return [
        label
        for label, phrases in RED_FLAGS.items()
        if any(_fold(phrase) in folded for phrase in phrases)
    ]


def _possibilities(symptom: str) -> list[Possibility]:
    folded = _fold(symptom)
    if any(word in folded for word in ("dau dau", "chong mat")):
        return [
            Possibility(name="Đau đầu do căng thẳng", note="Thường liên quan thiếu ngủ, căng thẳng hoặc mất nước."),
            Possibility(name="Đau nửa đầu", note="Cân nhắc khi đau theo nhịp, sợ ánh sáng hoặc buồn nôn."),
            Possibility(name="Viêm đường hô hấp hoặc xoang", note="Cân nhắc nếu kèm nghẹt mũi, đau vùng mặt hoặc sốt."),
        ]
    if any(word in folded for word in ("ho", "dau hong", "sot")):
        return [
            Possibility(name="Nhiễm virus đường hô hấp", note="Thường gây ho, đau họng, mệt và có thể sốt nhẹ."),
            Possibility(name="Viêm họng", note="Cân nhắc khi đau tăng lúc nuốt hoặc khàn tiếng."),
        ]
    if any(word in folded for word in ("dau bung", "tieu chay", "buon non")):
        return [
            Possibility(name="Rối loạn tiêu hóa", note="Có thể liên quan thức ăn, đầy hơi hoặc thay đổi thói quen ăn uống."),
            Possibility(name="Viêm dạ dày", note="Cân nhắc nếu đau vùng thượng vị, nóng rát hoặc buồn nôn."),
        ]
    return [
        Possibility(
            name="Cần thêm thông tin",
            note="Triệu chứng chưa đủ đặc hiệu để đưa ra nhóm nguyên nhân tham khảo.",
        )
    ]


def assess(request: TriageRequest) -> TriageResponse:
    combined = " ".join(part for part in (request.symptom, request.duration) if part)
    red_flags = find_red_flags(combined)
    if red_flags:
        return TriageResponse(
            urgency="emergency",
            reply=(
                "Mô tả có dấu hiệu có thể cần đánh giá khẩn cấp. Hãy gọi 115 hoặc "
                "đến cơ sở cấp cứu gần nhất ngay; không nên chờ tư vấn trực tuyến."
            ),
            disclaimer=DISCLAIMER,
            matched_red_flags=red_flags,
            next_step="Nếu có thể, hãy nhờ người thân đi cùng và không tự lái xe.",
        )

    if not request.duration:
        return TriageResponse(
            urgency="routine",
            reply=(
                "Cảm ơn bạn đã chia sẻ. Triệu chứng này bắt đầu từ khi nào? "
                "Bạn có thể chọn một mốc thời gian hoặc mô tả cụ thể hơn."
            ),
            disclaimer=DISCLAIMER,
        )

    return TriageResponse(
        urgency="routine",
        reply=(
            "Tôi đã tổng hợp thông tin ban đầu. Dưới đây là các nhóm khả năng "
            "tham khảo và bước tiếp theo phù hợp."
        ),
        disclaimer=DISCLAIMER,
        possibilities=_possibilities(request.symptom),
        next_step=(
            "Nghỉ ngơi, uống đủ nước và theo dõi triệu chứng. Đi khám nếu triệu "
            "chứng kéo dài, tăng dần, tái diễn hoặc ảnh hưởng sinh hoạt."
        ),
    )

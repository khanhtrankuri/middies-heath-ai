import re
import unicodedata

from .models import Possibility, TriageRequest, TriageResponse

DISCLAIMER = (
    "Thông tin này chỉ có tính tham khảo, không phải chẩn đoán y khoa và không "
    "thay thế việc thăm khám của bác sĩ."
)

RED_FLAGS: dict[str, tuple[str, ...]] = {
    "khó thở": ("kho tho", "khong tho duoc", "khong the tho", "cannot breathe", "can't breathe", "difficulty breathing", "shortness of breath"),
    "đau ngực": ("dau nguc", "tuc nguc", "chest pain", "chest pressure"),
    "ngất": ("ngat", "bat tinh", "unconscious", "passed out"),
    "co giật": ("co giat", "seizure"),
    "yếu hoặc liệt": ("yeu liet", "liet", "yeu mot ben", "one sided weakness"),
    "méo miệng": ("meo mieng",),
    "chảy máu nhiều": ("chay mau nhieu", "máu không cầm", "mau khong cam"),
    "rối loạn nói đột ngột": ("noi kho dot ngot", "dot ngot noi kho", "noi ngong dot ngot", "slurred speech"),
    "tím tái": ("moi tim tai", "tim moi", "blue lips"),
    "sưng đường thở": ("sung luoi", "sung hong", "swollen tongue", "throat swelling"),
    "nôn ra máu": ("non ra mau", "vomiting blood"),
    "đau đầu dữ dội đột ngột": ("dau dau du doi dot ngot", "dot ngot dau dau du doi", "sudden severe headache"),
}


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
    without_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_marks).strip()


def is_information_question(text: str) -> bool:
    """Only exempt clear educational questions without a personal symptom report."""
    folded = _fold(text)
    question = (
        r"(?:la gi\s*[?？]?$|\b(?:toi (?:muon|can) biet|cho toi biet|"
        r"liet ke|giai thich|thong tin ve|nguyen nhan cua|trieu chung cua|"
        r"dau hieu cua|what is|what are|tell me (?:about|what))\b)"
    )
    # A first-person pronoun alone does not turn an educational request such as
    # "Tôi muốn biết khó thở là gì?" into a symptom report. Conversely, an
    # explicit report remains safety-relevant even when it ends as a question.
    personal_report = (
        r"\b(?:toi|minh|em|chau|con toi|me toi|bo toi|i|my (?:mother|father|child))"
        r"\s+(?:bi|dang|vua|da|cam thay|thay|dau|tuc|kho|ngat|co giat|"
        r"cannot|can't|have|has|am|is)\b"
    )
    return bool(re.search(question, folded) and not re.search(personal_report, folded))


def symptom_present(text: str, phrase: str) -> bool:
    folded, needle = _fold(text), _fold(phrase)
    for match in re.finditer(r"\b" + re.escape(needle) + r"\b", folded):
        if needle == "liet" and re.match(r"\s+ke\b", folded[match.end():]):
            continue
        prefix = folded[:match.start()]
        if needle == "non" and re.search(r"\bbuon\s+$", prefix):
            continue
        # Coordination starts a new negation scope. Without this boundary,
        # "không sốt và đang khó thở" incorrectly negates "khó thở" too.
        clause = re.split(r"\b(?:va|nhung|ma|tuy nhien|and|but|however)\b|[,.;!?\n]", prefix)[-1]
        # "không chỉ", "không hết", "không giảm" do not deny the symptom.
        clause = re.sub(r"\b(?:khong (?:chi|het|giam)|not only)\b", "", clause)
        if re.search(r"\b(?:khong|chua|ko|no|not|without|deny|denies)\b(?:\s+\w+){0,4}\s*$", clause):
            continue
        return True
    return False


def find_red_flags(text: str) -> list[str]:
    if is_information_question(text):
        return []
    return [
        label
        for label, phrases in RED_FLAGS.items()
        if any(symptom_present(text, phrase) for phrase in phrases)
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

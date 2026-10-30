import os
import re
import unicodedata

from .models import Possibility, TriageRequest, TriageResponse

DISCLAIMER = (
    "Thông tin này chỉ có tính tham khảo, không phải chẩn đoán y khoa và không "
    "thay thế việc thăm khám của bác sĩ."
)

SELF_HARM_FLAG = "ý nghĩ tự tử hoặc tự hại"

# Phrases are matched without diacritics, except phrases that contain
# diacritics: "tự tử" folds to "tu tu", which is also "từ từ" (slowly).
RED_FLAGS: dict[str, tuple[str, ...]] = {
    "khó thở": (
        "kho tho", "khong tho duoc", "khong the tho", "tho khong noi", "hut hoi", "ngop tho",
        "nghet tho", "tho doc", "cannot breathe", "can't breathe", "difficulty breathing",
        "shortness of breath", "can't catch my breath",
    ),
    "đau ngực": ("dau nguc", "tuc nguc", "dau that nguc", "that nguc", "chest pain", "chest pressure"),
    "ngất": ("ngat", "bat tinh", "ngat xiu", "bi xiu", "xiu xuong", "xỉu", "unconscious", "passed out", "fainted"),
    "co giật": ("co giat", "seizure", "convulsion"),
    "yếu hoặc liệt": ("yeu liet", "liet", "yeu mot ben", "one sided weakness"),
    "méo miệng": ("meo mieng", "meo mat", "lech mieng", "facial droop"),
    "chảy máu nhiều": ("chay mau nhieu", "máu không cầm", "mau khong cam"),
    "rối loạn nói đột ngột": (
        "noi kho dot ngot", "dot ngot noi kho", "noi ngong dot ngot", "dot ngot noi ngong",
        "bong nhien noi ngong", "tu nhien noi ngong", "slurred speech",
    ),
    "tím tái": ("moi tim tai", "tim moi", "blue lips"),
    "sưng đường thở": ("sung luoi", "sung hong", "swollen tongue", "throat swelling"),
    "nôn ra máu": ("non ra mau", "vomiting blood"),
    "đau đầu dữ dội đột ngột": ("dau dau du doi dot ngot", "dot ngot dau dau du doi", "sudden severe headache"),
    "li bì hoặc khó đánh thức": ("li bi", "kho danh thuc", "khong danh thuc duoc", "lơ mơ", "unresponsive"),
    "ngộ độc hoặc quá liều": (
        "qua lieu", "uong ca vi", "uong het vi", "uong ca lo", "uong het lo", "uong ca hop",
        "uong nhieu thuoc", "uong thuoc tru sau", "uong hoa chat", "nuot hoa chat", "nuot pin",
        "ngo doc", "overdose", "overdosed", "poisoned", "swallowed poison",
    ),
    "phản vệ": ("phan ve", "soc phan ve", "anaphylaxis", "anaphylactic"),
    SELF_HARM_FLAG: (
        "tự tử", "tự sát", "tự vẫn", "tự hại", "muon tu tu", "dinh tu tu", "nghi den tu tu",
        "tu lam hai ban than", "muon chet", "khong muon song", "chan song", "ket lieu ban than",
        "ket lieu doi minh", "kill myself", "suicide", "suicidal", "end my life", "want to die",
        "self harm", "self-harm", "hurt myself",
    ),
}

# Red flags that need a context and a symptom in the same message, each affirmed.
COMBINED_RED_FLAGS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "chảy máu hoặc đau bụng dữ dội khi mang thai",
        r"\b(?:mang thai|co thai|co bau|dang bau|bau \d+|thai \d+ (?:tuan|thang)|pregnant)\b",
        ("ra mau", "chay mau", "bleeding", "dau bung du doi", "severe abdominal pain"),
    ),
    (
        "sốt hoặc bỏ bú ở trẻ dưới 3 tháng",
        r"(?:\bso sinh\b|\bnewborn\b|\b\d{1,2} (?:ngay|tuan) tuoi\b"
        r"|\b(?:be|con|chau|em be)(?: \w+)? \d{1,2} (?:ngay|tuan)\b|\b[0-2] thang tuoi\b"
        r"|\b(?:be|con|chau)(?: \w+)? [0-2] thang\b|\b\d{1,2} (?:days?|weeks?) old\b|\b[0-2] months? old\b)",
        ("sot", "fever", "bo bu", "refusing to feed"),
    ),
    (
        "phản vệ",
        r"\b(?:di ung|noi me day|me day|allergic|hives)\b",
        ("sung moi", "sung mat", "sung mi mat", "swollen lips", "face swelling", "choang", "tut huyet ap"),
    ),
)

# "đau bụng muốn chết" is an idiom for intensity; "đau khổ muốn chết" is not.
_IDIOM_BEFORE_DIE = r"\b(?:dau(?! kho\b)|met|doi|nong|lanh|ret|ngua|buon ngu|cuoi|so)\b(?: \w+){0,2}(?: qua)?\s*$"


def _fold(value: str, strip: bool = True) -> str:
    normalized = unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
    without_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    collapsed = re.sub(r"\s+", " ", without_marks)
    return collapsed.strip() if strip else collapsed


def _lower(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value.lower())).strip()


_EDU_PREFIX = r"^(?:(?:toi muon biet|toi can biet|cho toi biet|hay|vui long|xin)\s+)?"
_EDU_START = (
    _EDU_PREFIX + r"(?:giai thich|thong tin ve|nguyen nhan (?:cua|gay)|trieu chung|dau hieu|bieu hien"
    r"|liet ke (?:cac )?(?:trieu chung|dau hieu|nguyen nhan)|what (?:is|are|causes)|tell me about|explain)\b"
)
# Any subject or reporting word means the message may describe a real person.
_REPORT = (
    r"\b(?:toi|minh|me|bo|ong|vo|chong|chau|be|con toi|bi|dang|vua|cam thay|bat dau|bay gio|luc nay"
    r"|i|i'm|my|he|she|mom|dad|has|have|having|had|am|suddenly|now)\b"
)


def is_information_question(text: str) -> bool:
    """Exempt only a single-clause definition question with no person or report.

    "Mẹ đang khó thở, cho tôi biết phải làm gì" is an emergency report even
    though it asks for information, so the exemption must stay this narrow.
    """
    body = re.sub(r"[\s?？.]+$", "", _fold(text))
    if not body or re.search(r"[,.;:!?？\n]", body):
        return False
    if not (re.search(_EDU_START, body) or re.search(r"\bla gi$", body)):
        return False
    return not re.search(_REPORT, re.sub(_EDU_PREFIX, "", body))


def _affirmed(needle: str, prefix: str, suffix: str) -> bool:
    """`prefix`/`suffix` are the folded text before and after the match."""
    if needle == "liet" and re.match(r"\s*ke\b", suffix):
        return False
    if needle == "ngo doc" and re.match(r"\s*(?:thuc pham|thuc an)\b", suffix):
        return False
    if needle == "non" and re.search(r"\bbuon\s*$", prefix):
        return False
    if needle == "muon chet" and re.search(_IDIOM_BEFORE_DIE, prefix):
        return False
    # Coordination starts a new negation scope. Without this boundary,
    # "không sốt và đang khó thở" incorrectly negates "khó thở" too.
    clause = re.split(r"\b(?:va|nhung|ma|tuy nhien|and|but|however)\b|[,.;!?\n]", prefix)[-1]
    # "không chỉ", "không hết", "không giảm" do not deny the symptom.
    clause = re.sub(r"\b(?:khong (?:chi|het|giam)|not only)\b", "", clause)
    return not re.search(r"\b(?:khong|chua|ko|no|not|without|deny|denies)\b(?:\s+\w+){0,4}\s*$", clause)


def symptom_present(text: str, phrase: str) -> bool:
    accented = not phrase.isascii()
    haystack = _lower(text) if accented else _fold(text)
    needle = _lower(phrase) if accented else _fold(phrase)
    for match in re.finditer(r"\b" + re.escape(needle) + r"\b", haystack):
        prefix, suffix = _fold(haystack[:match.start()], strip=False), _fold(haystack[match.end():], strip=False)
        if _affirmed(_fold(needle), prefix, suffix):
            return True
    return False


def _context_present(text: str, pattern: str) -> bool:
    folded = _fold(text)
    return any(
        _affirmed(pattern, folded[:m.start()], folded[m.end():]) for m in re.finditer(pattern, folded)
    )


def find_red_flags(text: str) -> list[str]:
    if is_information_question(text):
        return []
    flags = [
        label
        for label, phrases in RED_FLAGS.items()
        if any(symptom_present(text, phrase) for phrase in phrases)
    ]
    for label, context, symptoms in COMBINED_RED_FLAGS:
        if label not in flags and _context_present(text, context) and any(symptom_present(text, s) for s in symptoms):
            flags.append(label)
    return flags


def emergency_reply(red_flags: list[str], country: str = "VN", phone: str = "115") -> str:
    medical = [flag for flag in red_flags if flag != SELF_HARM_FLAG]
    parts = []
    if SELF_HARM_FLAG in red_flags:
        crisis = os.getenv("MEDDIES_CRISIS_LINE", "").strip()
        parts.append(
            "Cảm ơn bạn đã chia sẻ điều này. Bạn không phải đối mặt với cảm giác này một mình. "
            f"Nếu bạn đang nghĩ đến việc làm hại bản thân hoặc không chắc mình an toàn lúc này, "
            f"hãy gọi {phone} hoặc đến cơ sở cấp cứu gần nhất ngay. Hãy liên hệ một người bạn "
            "tin tưởng và nhờ họ ở cạnh bạn."
            + (f" Bạn cũng có thể gọi {crisis} để được lắng nghe và hỗ trợ." if crisis else "")
        )
    if medical:
        parts.append(
            f"Mô tả có dấu hiệu có thể cần đánh giá khẩn cấp: {', '.join(medical)}. "
            f"Nếu bạn ở {country}, hãy gọi {phone} hoặc đến cơ sở cấp cứu gần nhất ngay; "
            "không chờ tư vấn trực tuyến."
        )
    return " ".join(parts)


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
            reply=emergency_reply(red_flags),
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

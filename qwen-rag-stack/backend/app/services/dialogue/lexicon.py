"""Vietnamese symptom and slot lexicon shared by state tracking and evaluation.

Matching runs on a diacritic-folded copy of the text whose characters align
one-to-one with the original, so spans found in the folded text can be mapped
back to what the user actually wrote. Terms that become ambiguous without
diacritics ("ho" cough vs "họ" they, "đau họng" throat vs "đau hông" hip)
carry accented patterns that are used whenever the message itself is
written with diacritics.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.triage import _affirmed

_VIETNAMESE_MARKS = re.compile(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]")


def fold_aligned(text: str) -> str:
    """Lowercase and strip diacritics while preserving string length."""
    out = []
    for char in unicodedata.normalize("NFC", text).lower():
        if char == "đ":
            out.append("d")
            continue
        base = "".join(
            part for part in unicodedata.normalize("NFD", char) if unicodedata.category(part) != "Mn"
        )
        out.append(base if len(base) == 1 else char)
    return "".join(out)


def normalize(text: str) -> str:
    """NFC + lowercase with single spaces; keeps length aligned with fold_aligned."""
    return unicodedata.normalize("NFC", text).lower()


def has_diacritics(text: str) -> bool:
    return bool(_VIETNAMESE_MARKS.search(normalize(text)))


@dataclass(frozen=True)
class Match:
    label: str
    start: int
    end: int
    text: str
    affirmed: bool


@dataclass(frozen=True)
class Term:
    """A symptom or feature with folded (ASCII) and optional accented patterns."""

    label: str
    folded: tuple[str, ...]
    accented: tuple[str, ...] = ()
    not_after: str | None = None  # folded regex that must not end right before the match
    key: str = ""

    def __post_init__(self) -> None:
        if not self.key:
            object.__setattr__(self, "key", re.sub(r"\W+", "_", fold_aligned(self.label)).strip("_"))


def find_term(text: str, term: Term, *, require_affirmed: bool | None = None) -> list[Match]:
    """Return every occurrence of `term` with its negation status.

    `require_affirmed=None` returns both affirmed and negated matches.
    """
    original = normalize(text)
    folded = fold_aligned(text)
    if term.accented and has_diacritics(text):
        haystack, patterns = original, term.accented
    else:
        haystack, patterns = folded, term.folded
    matches: list[Match] = []
    seen: set[tuple[int, int]] = set()
    for pattern in patterns:
        for found in re.finditer(rf"(?<!\w)(?:{pattern})(?!\w)", haystack):
            span = (found.start(), found.end())
            if span in seen:
                continue
            prefix, suffix = folded[: found.start()], folded[found.end() :]
            if term.not_after and re.search(rf"(?:{term.not_after})\s*$", prefix):
                continue
            seen.add(span)
            affirmed = _affirmed(folded[found.start() : found.end()], prefix, suffix)
            if require_affirmed is not None and affirmed != require_affirmed:
                continue
            matches.append(Match(term.label, *span, text[found.start() : found.end()], affirmed))
    return sorted(matches, key=lambda item: item.start)


def first_match(text: str, patterns: tuple[str, ...]) -> re.Match[str] | None:
    """First folded-regex match; the returned span indexes the original text."""
    folded = fold_aligned(text)
    best: re.Match[str] | None = None
    for pattern in patterns:
        found = re.search(rf"(?<!\w)(?:{pattern})(?!\w)", folded)
        if found and (best is None or found.start() < best.start()):
            best = found
    return best


# --- Symptoms ---------------------------------------------------------------

SYMPTOMS: tuple[Term, ...] = (
    Term("đau đầu", ("dau dau", "nhuc dau", "dau nua dau", "dau dau du doi", "nhuc nua dau"), key="dau_dau"),
    Term("đau bụng", ("dau bung", "dau da day", "dau thuong vi", "dau quan bung", "dau quanh ron", "dau vung bung", "dau bao tu"), key="dau_bung"),
    Term("sốt", ("sot", "sot cao", "sot nhe", "phat sot", "bi sot", "nong sot", "sot ret"),
         ("sốt",), key="sot"),
    Term("ho", (r"(?:bi|dang|con|hay|van|cu|bat dau) ho", r"ho (?:khan|dom|co dom|nhieu|keo dai|ra|lien tuc|tung con|ve dem|ban dem|suot)"),
         ("ho",), key="ho"),
    Term("đau họng", ("dau hong", "rat hong", "vuong hong", "viem hong", "ngua hong"),
         ("đau họng", "rát họng", "vướng họng", "viêm họng", "ngứa họng", "đau rát họng"), key="dau_hong"),
    Term("sổ mũi", ("so mui", "chay nuoc mui", "chay mui"), key="so_mui"),
    Term("nghẹt mũi", ("nghet mui", "tac mui", "ngat mui"), key="nghet_mui"),
    Term("hắt hơi", ("hat hoi",), key="hat_hoi"),
    Term("khó thở", ("kho tho", "hut hoi", "tho doc", "tho khong noi"), key="kho_tho"),
    Term("thở khò khè", ("kho khe", "tho rit"), key="kho_khe"),
    Term("đau ngực", ("dau nguc", "tuc nguc", "nang nguc"), key="dau_nguc"),
    Term("buồn nôn", ("buon non", "buon oi", "lom giong", "nao nao"), key="buon_non"),
    Term("nôn", (r"(?:bi|da|con|hay) non", "non oi", "non mua", "oi mua", "non nhieu", r"non ra", r"bi oi"),
         ("nôn", "ói", "mửa", "nôn ói", "nôn mửa"), not_after=r"buon", key="non"),
    Term("tiêu chảy", ("tieu chay", "di ngoai long", "di long", "phan long", "di ngoai nhieu lan"), key="tieu_chay"),
    Term("táo bón", ("tao bon",), key="tao_bon"),
    Term("đi ngoài ra máu", ("di ngoai ra mau", "phan co mau", "phan den", "di cau ra mau"), key="phan_mau"),
    Term("chóng mặt", ("chong mat", "hoa mat", "choang vang", "xay xam", "quay cuong"), key="chong_mat"),
    Term("mệt mỏi", ("met moi", "ue oai", "kiet suc", "nguoi met", "met nhieu", "uon nguoi", r"(?:bi|thay|hoi|rat|dang) met"),
         ("mệt", "mệt mỏi", "uể oải", "kiệt sức", "đuối sức"), key="met_moi"),
    Term("đau nhức cơ", ("dau nhuc co the", "dau moi nguoi", "dau nhuc nguoi", "nhuc moi", "dau co bap"),
         ("đau nhức cơ", "đau cơ", "nhức mỏi", "đau mỏi người", "đau nhức người", "đau nhức cơ thể", "đau cơ bắp"), key="dau_co"),
    Term("phát ban", ("phat ban", "noi ban", "man do", "noi mun do", "noi do", "chan do"), key="phat_ban"),
    Term("nổi mề đay", ("me day", "noi me day", "noi man ngua"), key="me_day"),
    Term("ngứa", (r"bi ngua", r"ngua (?:nhieu|ngay|khap|da)", "ngua ngay"), ("ngứa",), key="ngua"),
    Term("đau lưng", ("dau lung", "dau that lung", "moi lung", "dau cot song"), key="dau_lung"),
    Term("đau khớp", ("dau khop", "sung khop", "dau goi", "dau co tay", "dau co chan", "dau vai", "cung khop"),
         ("đau khớp", "sưng khớp", "đau gối", "đau cổ tay", "đau cổ chân", "đau vai", "cứng khớp", "đau mắt cá"), key="dau_khop"),
    Term("tiểu buốt", ("tieu buot", "tieu rat", "dau rat khi di tieu", "buot khi di tieu", "tieu nhieu lan", "tieu gat", "rat khi tieu"), key="tieu_buot"),
    Term("tiểu ra máu", ("tieu ra mau", "nuoc tieu co mau", "nuoc tieu (?:mau )?hong", "nuoc tieu do"), key="tieu_mau"),
    Term("đau tai", ("dau tai", "u tai", "chay mu tai", "nghe kem"), key="dau_tai"),
    Term("đau mắt", ("dau mat", "mat do", "ngua mat", "chay nuoc mat", "co ghen mat"),
         ("đau mắt", "mắt đỏ", "đỏ mắt", "ngứa mắt", "chảy nước mắt", "có ghèn"), key="dau_mat"),
    Term("mất ngủ", ("mat ngu", "kho ngu", "ngu khong ngon"), key="mat_ngu"),
    Term("sụt cân", ("sut can", "gay sut", "sut ky"), key="sut_can"),
    Term("hồi hộp", ("hoi hop", "danh trong nguc", "tim dap nhanh"), key="hoi_hop"),
    Term("khó nuốt", ("kho nuot", "nuot dau", "nuot vuong"), key="kho_nuot"),
    Term("ợ chua", ("o chua", "o nong", "trao nguoc", "o hoi"), key="o_chua"),
    Term("đầy hơi", ("day hoi", "chuong bung", "day bung", "kho tieu"), key="day_hoi"),
    Term("phù", ("phu chan", "phu mat", "sung phu", "phu nhe", "phu hai chan"), ("phù",), key="phu"),
    Term("tê bì", ("te bi", "te tay", "te chan", "te buot", "te nua nguoi"), key="te_bi"),
    Term("sưng", (r"bi sung", r"sung (?:dau|to|do|len|nhieu)"), ("sưng",), key="sung"),
    Term("co giật", ("co giat",), key="co_giat"),
    Term("ngất", ("ngat xiu", "bat tinh", "xiu"), ("ngất", "ngất xỉu", "bất tỉnh", "xỉu"), key="ngat"),
    Term("chảy máu", ("chay mau",), key="chay_mau"),
    Term("khàn tiếng", ("khan tieng", "mat tieng"), key="khan_tieng"),
    Term("cứng cổ", ("cung co", "co cung", "gay cung"), ("cứng cổ", "cổ cứng", "gáy cứng"), key="cung_co"),
    Term("sợ ánh sáng", ("so anh sang", "choi mat", "kho chiu voi anh sang"), key="so_anh_sang"),
    Term("đau hông lưng", ("dau hong lung", "dau mang suon", "dau vung than"),
         ("đau hông lưng", "đau hông", "đau mạng sườn", "đau vùng thận", "đau một bên hông"), key="dau_hong_lung"),
    Term("yếu liệt", ("yeu liet", "yeu mot ben", r"bi liet", r"liet (?:nua|mot|tay|chan)"), key="yeu_liet"),
    Term("nói khó", ("noi kho", "noi ngong", "noi lap"), key="noi_kho"),
    Term("lơ mơ", ("lo mo", "li bi", "kho danh thuc"), key="lo_mo"),
)
SYMPTOM_BY_KEY = {term.key: term for term in SYMPTOMS}


# --- Slots ------------------------------------------------------------------

SLOT_LABELS: dict[str, str] = {
    "timing": "thời điểm bắt đầu / thời gian kéo dài",
    "location": "vị trí",
    "severity": "mức độ",
    "character": "tính chất triệu chứng",
    "progression": "diễn biến",
    "triggers": "yếu tố làm nặng hoặc giảm",
    "associated_symptoms": "triệu chứng đi kèm",
    "red_flag_screen": "sàng lọc dấu hiệu nguy hiểm",
    "relevant_history": "tiền sử bệnh",
    "medications": "thuốc đang dùng",
    "allergies": "dị ứng",
    "age": "tuổi",
}

DURATION_PATTERNS = (
    r"(?:khoang |duoc |keo dai |duoi |tren |gan |hon |ca )?\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+)?\s*(?:phut|tieng|gio|ngay|tuan|thang|nam|minutes?|hours?|days?|weeks?|months?|years?)(?: nay| roi| qua| truoc)?",
    r"(?:mot|hai|ba|bon|nam|vai|may|muoi) (?:hom|ngay|tuan|thang|nam|bua)(?: nay| roi| qua)?",
    r"(?:tu )?(?:hom qua|hom kia|sang nay|chieu nay|toi qua|dem qua|toi hom qua|sang hom qua|trua nay|chieu qua|tuan truoc|thang truoc|nam ngoai)",
    # A bare "hôm nay" is usually the visit ("hôm nay em đến khám"), not onset.
    r"tu (?:hom nay|tuan nay)|(?:bi|bat dau|xuat hien) (?:tu )?hom nay",
    r"(?:may|vai|mot vai) hom(?: nay)?",
    r"(?:moi|vua) (?:bi|bat dau|xuat hien)",
    # "Đột ngột" describes how symptoms began (feature onset:sudden), not when.
    r"lau roi|lau nay|ke tu (?:khi|luc)\s\w+",
    r"today|yesterday|since (?:this morning|last night)",
)
AGE_PATTERN = r"\d{1,3}\s*(?:(?:thang|nam)\s*)?(?:tuoi|years? old|months? old)"

SEVERITY_PATTERNS = (
    r"(?:muc\s*)?\d{1,2}\s*/\s*10",
    r"muc(?: do)? \d{1,2}",
    r"\d{1,2} diem",
    r"(?:dau|ho|sot|ngua|met|chong mat|non|kho chiu|nhuc)(?: \w+){0,2} (?:rat |hoi |kha |cuc ky |qua |vo cung )?(?:nhe|vua phai|nang|du doi|nhieu|kinh khung|ghe gom)",
    r"muc do (?:rat |hoi |kha )?(?:nhe|vua|vua phai|nang|trung binh)",
    r"(?:dau |ho )?(?:du doi|khong chiu noi|khong chiu duoc|chiu duoc|kinh khung|nhe thoi|cung nhe|hoi nhe|kha nang|rat nang|chi nhe)",
    r"(?:sot|nhiet do|do duoc|len toi|len den|cao nhat)\s*(?:khoang |la |len )?\d{2}(?:[.,]\d)?\s*(?:do)?",
    r"\d{2}(?:[.,]\d)?\s*do(?: c)?",
)
LOCATION_PATTERNS = (
    r"(?:vung |o |phia |ben )?(?:thuong vi|ha vi|quanh ron|tren ron|duoi ron|ho chau (?:phai|trai)|ha suon (?:phai|trai)|bung tren|bung duoi(?: ben (?:phai|trai))?|mang suon(?: (?:phai|trai))?|khap bung|ca bung)",
    r"(?:nua dau|mot ben dau|hai ben dau|ca dau|vung tran|tran|thai duong|sau gay|dinh dau|gay|hoc mat|sau mat|quanh mat)",
    r"(?:nguc (?:trai|phai|giua)|giua nguc|sau xuong uc)",
    r"(?:that lung|lung duoi|lung tren|cot song|hong lung)",
    r"(?:ben (?:trai|phai)|phia (?:trai|phai)|mot ben|hai ben|ca hai ben)",
    r"(?:dau goi|co tay|co chan|mat ca|khop (?:goi|vai|hang|khuyu)|vai|ban tay|ban chan|ngon tay|ngon chan)",
    r"(?:co hong|hong|amidan|tai (?:trai|phai)|mat (?:trai|phai))",
)
CHARACTER_PATTERNS = (
    r"am i", r"quan(?: tung con| tung dot)?", r"nhoi(?: nhoi)?", r"nhu dao dam", r"nhu kim dam",
    r"bong rat|nong rat|rat bong", r"cang tuc|tuc nang|de nang|that chat|bop chat|nang dau",
    r"theo nhip|giat giat|bung bung|nhuc nhoi", r"ho khan|ho co dom|ho dom|dom (?:vang|xanh|trang|trong|dac|co mau)",
    r"buot|chan chat|ran ran",
)
PROGRESSION_PATTERNS = (
    r"tang dan|nang dan|nang hon|ngay cang|giam dan|do hon|do dan|bot dan|khong thay doi|van vay|nhu cu",
    r"lien tuc|tung con|tung dot|luc co luc khong|luc dau luc khong|tai di tai lai|hay tai phat|thinh thoang|lap lai",
    r"di chuyen (?:xuong|sang)|lan (?:xuong|ra|sang|len)",
)
TRIGGER_PATTERNS = (
    r"sau (?:khi )?an|khi doi|luc doi|bung doi|khi an|an do (?:cay|dau mo|chua)|sau bua an|an no",
    r"khi (?:van dong|gang suc|di lai|leo cau thang|nam|ngoi|dung|cui|xoay|ho|hit sau|nuot|cu dong|tho sau)",
    r"ve dem|ban dem|buoi sang|luc sang|khi ngu day|thay doi thoi tiet|tiep xuc|sau khi (?:tap|mang vac|khieng|nang)",
    r"nghi ngoi (?:thi |se )?(?:do|giam)|uong thuoc (?:thi |vao )?(?:do|giam)",
)
HISTORY_TERMS = (
    r"tang huyet ap|cao huyet ap|huyet ap cao|tieu duong|dai thao duong|duong huyet cao",
    r"hen suyen|hen phe quan|bi hen|benh tim|suy tim|thieu mau co tim|benh than|suy than|soi than|soi mat|viem gan",
    r"viem da day|dau da day|trao nguoc|copd|phoi tac nghen|dong kinh|ung thu|lao phoi|gout|mo mau cao|roi loan mo mau",
    r"tien su (?:\w+ ?){1,4}|tung bi (?:\w+ ?){1,4}|benh nen (?:la )?(?:\w+ ?){1,3}",
)
HISTORY_NONE = (
    r"khong (?:co )?benh nen|khong co tien su|chua tung bi benh gi|khong co benh gi|khoe manh binh thuong|truoc gio khoe",
    r"khong (?:co )?benh (?:gi|ly gi)(?: truoc do| khac)?|khong bi benh gi",
)
MEDICATION_TERMS = (
    r"paracetamol|panadol|efferalgan|hapacol|ibuprofen|aspirin|omeprazole|esomeprazole|berberin|smecta|oresol|motilium|amoxicillin|augmentin|cefuroxim|metformin|amlodipin(?:e)?|losartan|salbutamol|ventolin|loratadin(?:e)?|cetirizin(?:e)?|corticoid|prednisolon",
    r"(?:dang|da|co|tu mua|tu) (?:uong|dung|xit|boi|tiem) thuoc(?: \w+){0,3}",
    r"thuoc (?:ha sot|giam dau|huyet ap|tieu duong|da day|khang sinh|ho|cam|di ung|bac|nam)",
    r"khang sinh",
)
MEDICATION_NONE = (
    r"(?:khong|chua) (?:uong|dung|su dung|xai) (?:thuoc|gi|thuoc gi)(?: ca| het)?",
    r"khong (?:dang )?(?:dung|uong) thuoc nao",
)
ALLERGY_TERMS = (r"di ung (?:voi )?(?:thuoc )?(?!gi\b)(?:\w+ ?){1,3}",)
ALLERGY_NONE = (r"khong (?:bi |co )?di ung(?: (?:voi )?(?:thuoc )?(?:gi|nao))?(?: ca| het)?", r"chua (?:tung )?(?:bi )?di ung")
PREGNANCY_PATTERN = r"mang thai|co thai|co bau|dang bau|thai \d+ (?:tuan|thang)"
NEGATIVE_ANSWER = re.compile(
    r"^(?:da |vang |da vang |thua bac si |bac si oi |)?(?:khong|ko|k|chua|khong co|chua co|khong a|khong co a|chua tung|khong bi|khong he|hoan toan khong|no)\b",
)
AFFIRMATIVE_ANSWER = re.compile(r"^(?:da |vang |da vang )?(?:co|co a|dung|dung roi|vang|da co|yes)\b")


@dataclass
class QuestionTopic:
    slots: set[str] = field(default_factory=set)
    symptoms: set[str] = field(default_factory=set)


# Keyword cues that a *question* is about a given slot. Matched on the folded
# text of one interrogative sentence.
QUESTION_SLOT_CUES: dict[str, tuple[str, ...]] = {
    "timing": (r"bao lau|khi nao|tu luc nao|tu bao gio|bat dau|keo dai|may ngay|bao nhieu ngay|tu hom nao|xuat hien tu|bi (?:duoc )?bao lau|thoi gian",),
    "location": (r"o dau|vi tri|cho nao|vung nao|ben nao|phia nao|cho nao|lan (?:ra|xuong|sang) dau|o vung",),
    "severity": (r"muc do|bao nhieu diem|may diem|thang (?:diem|0|1|10)|tren 10|/10|10 la|nang (?:khong|lam khong)|bao nhieu do|nhiet do|do (?:duoc )?bao nhieu|sot cao nhat",),
    "character": (r"nhu the nao|cam giac (?:nhu|ra sao|the nao)|kieu|am i|quan|nhoi|bong rat|nong rat|ho khan hay|co dom|dom mau|tinh chat|mo ta (?:con|cam giac)",),
    "progression": (r"tang (?:len|dan)|giam (?:di|dan)|dien bien|lien tuc|tung con|luc co luc khong|nang hon|do hon|tai phat|lap lai|bao nhieu lan",),
    "triggers": (r"sau (?:khi )?an|khi doi|khi van dong|yeu to|lam (?:cho )?(?:dau|trieu chung) nang|lam giam|do hon khi|nang hon khi|khi nam|tu the|tiep xuc|an gi|an uong",),
    "associated_symptoms": (r"kem theo|di kem|(?<!\w)kem(?!\w)|trieu chung (?:nao )?khac|con (?:bi|thay) gi|co (?:bi |thay )?(?:sot|non|buon non|tieu chay|ho|kho tho|chong mat|met|phat ban|ngua|so mui|dau hong|te|o chua)",),
    "red_flag_screen": (r"kho tho|dau nguc|yeu (?:hoac |hay )?(?:liet|te)|meo mieng|noi kho|ngat|co giat|non ra mau|phan den|cung co|lo mo|li bi|du doi dot ngot|dot ngot du doi|xuat huyet|moi tim|ho ra mau|bung cung|khong chiu noi",),
    "relevant_history": (r"tien su|benh nen|benh ly nen|benh man tinh|tung bi|benh (?:gi|ly gi) (?:khac|truoc)|huyet ap|tieu duong|tien can",),
    "medications": (r"thuoc|dang uong|da uong|da dung|dang dung|dieu tri gi",),
    "allergies": (r"di ung",),
    "age": (r"bao nhieu tuoi|tuoi",),
}


def split_questions(text: str) -> list[str]:
    """Split a reply into interrogative sentences (ending with '?').

    Statements that precede a question in the same paragraph ("Bé 4 tuổi bị
    đau bụng. Cơn đau có dữ dội không?") are separate sentences and must not
    contribute slot cues to the question.
    """
    pieces = re.split(r"(?<=[?？.!…])\s+|\n+|(?<=\d)\.\s", text)
    return [piece.strip() for piece in pieces if piece.strip().endswith(("?", "？"))]


def question_topics(text: str) -> QuestionTopic:
    """Slots (and specific symptoms) that the questions in `text` ask about."""
    topic = QuestionTopic()
    for question in split_questions(text):
        folded = fold_aligned(question)
        for slot, cues in QUESTION_SLOT_CUES.items():
            if any(re.search(cue, folded) for cue in cues):
                topic.slots.add(slot)
        # "Mỗi cơn kéo dài bao lâu?" asks about episode length, not onset.
        if "timing" in topic.slots and re.search(r"moi (?:lan|con|dot|khi)|tung con", folded) \
                and not re.search(r"bat dau|tu khi nao|tu bao gio|tu luc nao", folded):
            topic.slots.discard("timing")
            topic.slots.add("progression")
        for term in SYMPTOMS:
            if find_term(question, term):
                topic.symptoms.add(term.key)
    # "Thuốc" in an allergy question is about allergy, not current medicines.
    if "allergies" in topic.slots and not re.search(r"dang uong|da uong|dang dung|da dung", fold_aligned(text)):
        topic.slots.discard("medications")
    return topic

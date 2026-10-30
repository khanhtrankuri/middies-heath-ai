"""Discrete clinical feature tokens derived only from user-reported text.

Feature tokens are the shared vocabulary between the dialogue state, the
question planner (information gain) and the hypothesis knowledge base:

* ``sym:<key>`` / ``neg:<key>`` — a symptom reported present / explicitly absent
* ``loc:*``, ``char:*``, ``trig:*``, ``prog:*`` — location, character,
  triggers and progression, each belonging to the planner slot of that name
* ``dur:*`` / ``onset:sudden`` — duration bucket derived from the timing slot
* ``hist:*`` / ``expo:*`` — relevant history and exposures
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .lexicon import fold_aligned


@dataclass(frozen=True)
class Feature:
    token: str
    slot: str
    label: str
    patterns: tuple[str, ...]


FEATURES: tuple[Feature, ...] = (
    # Location
    Feature("loc:thuong_vi", "location", "vùng thượng vị (trên rốn)", (r"thuong vi|tren ron|vung da day|bung tren|vung uc|mo ac|vung bao tu",)),
    Feature("loc:quanh_ron", "location", "quanh rốn", (r"quanh ron|giua bung|xung quanh ron",)),
    Feature("loc:ho_chau_phai", "location", "bụng dưới bên phải", (r"ho chau phai|bung duoi ben phai|bung ben phai phia duoi|duoi ben phai|goc duoi ben phai",)),
    Feature("loc:ha_suon_phai", "location", "dưới sườn phải", (r"ha suon phai|duoi suon phai|bung tren ben phai|duoi bo suon phai",)),
    Feature("loc:bung_duoi", "location", "bụng dưới / trên xương mu", (r"bung duoi(?! ben)|ha vi|tren xuong mu|vung bang quang|duoi ron|bung duoi giua",)),
    Feature("loc:lan_toa_bung", "location", "khắp bụng", (r"khap bung|ca bung|lan toa|quan khap",)),
    Feature("loc:mot_ben_dau", "location", "một bên đầu", (r"nua dau|mot ben dau|dau (?:ben )?(?:trai|phai)|ben (?:trai|phai) dau|thai duong (?:ben )?(?:trai|phai)",)),
    Feature("loc:hai_ben_dau", "location", "hai bên / cả đầu", (r"hai ben dau|ca dau|khap dau|quanh dau|nhu deo vong|ca hai ben|hai ben thai duong|dinh dau",)),
    Feature("loc:tran_mat", "location", "vùng trán / quanh mắt / mặt", (r"vung tran|(?<!\w)tran(?!\w)|quanh mat|hoc mat|go ma|sau mat|vung mat",)),
    Feature("loc:sau_gay", "location", "sau gáy", (r"sau gay|vung gay|(?<!\w)gay(?!\w)",)),
    Feature("loc:hong_lung", "location", "hông lưng / mạng sườn", (r"hong lung|mang suon|vung than|eo lung mot ben|hai ben hong",)),
    Feature("loc:lung_duoi", "location", "thắt lưng", (r"that lung|lung duoi|cot song that lung|vung lung duoi",)),
    Feature("loc:lan_xuong_chan", "location", "lan xuống mông/chân", (r"lan xuong (?:chan|mong|dui|bap chan)|xuong mong|lan ra (?:chan|mong)",)),
    Feature("loc:co_hong", "location", "cổ họng", (r"co hong|trong hong|amidan",)),
    Feature("loc:toan_than", "location", "toàn thân", (r"toan than|khap nguoi|ca nguoi|khap co the",)),
    Feature("loc:tay_chan", "location", "tay / chân", (r"(?<!\w)(?:tay|chan|canh tay|cang chan|ban tay|ban chan)(?!\w)",)),
    # Character
    Feature("char:nong_rat", "character", "nóng rát", (r"nong rat|bong rat|rat bong|xot ruot|cuon cuon",)),
    Feature("char:quan", "character", "quặn từng cơn", (r"(?<!\w)quan(?!\w)|dau quan|quan that",)),
    Feature("char:am_i", "character", "âm ỉ", (r"am i",)),
    Feature("char:theo_nhip", "character", "đau theo nhịp mạch / giật giật", (r"theo nhip|giat giat|bung bung|nhoi theo nhip|dap thinh thich",)),
    Feature("char:that_chat", "character", "căng, thắt chặt / đè nặng", (r"that chat|bop chat|nang dau|de nang|cang nhu|cang tuc|nhu deo vong",)),
    Feature("char:ho_khan", "character", "ho khan", (r"ho khan",)),
    Feature("char:ho_dom", "character", "ho có đờm", (r"ho (?:co )?dom|khac (?:ra )?dom|dom (?:vang|xanh|trang|dac|trong)",)),
    Feature("char:dom_mu", "character", "đờm vàng/xanh", (r"dom (?:vang|xanh|dac|mu)",)),
    Feature("char:te_lan", "character", "tê, như điện giật", (r"te lan|dien giat|te buot|te bi",)),
    Feature("char:quay_cuong", "character", "cảm giác quay cuồng", (r"quay cuong|nha cua quay|moi thu quay|quay vong",)),
    # Triggers
    Feature("trig:sau_an", "triggers", "nặng hơn sau ăn", (r"sau (?:khi )?an|an no|sau bua an|an xong",)),
    Feature("trig:an_dau_mo", "triggers", "sau ăn đồ nhiều dầu mỡ", (r"an (?:do )?(?:dau mo|chien|ran|nhieu mo|beo)",)),
    Feature("trig:khi_doi", "triggers", "đau khi đói", (r"khi doi|luc doi|bung doi|bo bua|nhin an",)),
    Feature("trig:van_dong", "triggers", "liên quan vận động / mang vác", (r"khi (?:van dong|gang suc|di lai|cu dong|cui|mang vac)|sau khi (?:mang|khieng|nang|be|tap)|mang vac nang|khieng do|nang do nang",)),
    Feature("trig:tu_the", "triggers", "khi thay đổi tư thế / xoay đầu", (r"khi (?:nam|xoay dau|quay dau|ngoi day|dung day|cui dau|tro minh|lan)|doi tu the|xoay nguoi",)),
    Feature("trig:cang_thang", "triggers", "căng thẳng / thiếu ngủ", (r"cang thang|stress|ap luc|thieu ngu|lam viec nhieu|thuc khuya|lam viec may tinh",)),
    Feature("trig:tiep_xuc", "triggers", "tiếp xúc chất lạ / dị nguyên", (r"tiep xuc|hoa chat|my pham|bot giat|phan hoa|(?<!\w)bui(?!\w)|long (?:cho|meo|thu)|thuoc moi|kem moi|sua tam moi",)),
    Feature("trig:an_la", "triggers", "ăn đồ lạ / nghi thức ăn không đảm bảo", (r"an (?:do )?(?:la|o ngoai|via he|hai san|song|tai)|do an (?:de lau|o thiu|thiu)|tiem an|an cung (?:nhau|ca nha)",)),
    Feature("trig:thoi_tiet", "triggers", "thay đổi thời tiết / lạnh", (r"thay doi thoi tiet|troi lanh|giao mua|tam mua|di mua",)),
    # Progression
    Feature("prog:tang_dan", "progression", "tăng dần", (r"tang dan|nang dan|nang hon|ngay cang|dau hon|tang len",)),
    Feature("prog:tung_con", "progression", "từng cơn", (r"tung con|tung dot|luc co luc khong|luc dau luc khong",)),
    Feature("prog:tai_phat", "progression", "hay tái phát", (r"tai di tai lai|hay tai phat|lap lai|nhieu lan roi|thuong xuyen bi|hay bi|moi thang|da tung bi|hay tai di",)),
    Feature("prog:di_chuyen", "progression", "đau di chuyển vị trí", (r"di chuyen (?:xuong|sang)|chuyen (?:xuong|sang)|luc dau o .{1,25} sau do|roi (?:chuyen|lan) xuong",)),
    Feature("prog:giam_dan", "progression", "giảm dần", (r"giam dan|do dan|bot dan|do hon|giam bot",)),
    # Onset
    Feature("onset:sudden", "timing", "khởi phát đột ngột", (r"dot ngot|bat ngo|tu nhien (?:bi|len)|bong nhien",)),
    # History
    Feature("hist:hen", "relevant_history", "tiền sử hen", (r"hen suyen|hen phe quan|bi hen|suyen",)),
    Feature("hist:di_ung", "relevant_history", "cơ địa dị ứng", (r"co dia di ung|viem mui di ung|hay di ung|da nhay cam|viem da co dia",)),
    Feature("hist:soi", "relevant_history", "tiền sử sỏi", (r"soi than|soi mat|soi tiet nieu|soi niem",)),
    Feature("hist:da_day", "relevant_history", "tiền sử bệnh dạ dày", (r"viem da day|dau da day|trao nguoc|loet da day|benh da day|hp duong tinh",)),
    Feature("hist:tang_huyet_ap", "relevant_history", "tăng huyết áp", (r"tang huyet ap|cao huyet ap|huyet ap cao",)),
    Feature("hist:tieu_duong", "relevant_history", "đái tháo đường", (r"tieu duong|dai thao duong|duong huyet cao",)),
    # Exposures
    Feature("expo:nguoi_benh", "triggers", "người xung quanh cũng bị", (r"nguoi nha (?:cung|cung dang) bi|nhieu nguoi (?:cung )?bi|lay tu|tiep xuc voi nguoi (?:bi|benh)|ca nha (?:cung )?bi|dong nghiep (?:cung )?bi",)),
    Feature("expo:muoi", "triggers", "vùng có muỗi / sốt xuất huyết", (r"muoi dot|bi muoi|sot xuat huyet|hang xom bi sot",)),
)
FEATURE_BY_TOKEN = {feature.token: feature for feature in FEATURES}


def symptom_feature_label(key: str) -> str:
    from .lexicon import SYMPTOM_BY_KEY

    term = SYMPTOM_BY_KEY.get(key)
    return term.label if term else key


def feature_label(token: str) -> str:
    if token.startswith(("sym:", "neg:")):
        label = symptom_feature_label(token.split(":", 1)[1])
        return label if token.startswith("sym:") else f"không {label}"
    if token in FEATURE_BY_TOKEN:
        return FEATURE_BY_TOKEN[token].label
    return {
        "dur:hours": "khởi phát trong vòng 24 giờ",
        "dur:acute": "kéo dài dưới 1 tuần",
        "dur:subacute": "kéo dài 1–4 tuần",
        "dur:chronic": "kéo dài trên 4 tuần",
        "sym:sot_cao": "sốt cao (từ 39°C)",
    }.get(token, token)


def feature_slot(token: str) -> str:
    if token.startswith(("sym:", "neg:")):
        return "associated_symptoms"
    if token.startswith("dur:"):
        return "timing"
    feature = FEATURE_BY_TOKEN.get(token)
    return feature.slot if feature else "associated_symptoms"


def extract_text_features(text: str) -> set[str]:
    """Affirmed feature tokens; "không đau sau ăn" does not yield trig:sau_an."""
    from app.triage import _affirmed

    folded = fold_aligned(text)
    found: set[str] = set()
    for feature in FEATURES:
        for pattern in feature.patterns:
            if any(
                _affirmed(match.group(0), folded[: match.start()], folded[match.end() :])
                for match in re.finditer(rf"(?<!\w)(?:{pattern})(?!\w)", folded)
            ):
                found.add(feature.token)
                break
    return found


_UNIT_DAYS = {
    "phut": 1 / 1440, "minute": 1 / 1440, "tieng": 1 / 24, "gio": 1 / 24, "hour": 1 / 24,
    "ngay": 1, "hom": 1, "bua": 1, "day": 1, "tuan": 7, "week": 7, "thang": 30, "month": 30,
    "nam": 365, "year": 365,
}
_WORD_NUMBERS = {"mot": 1, "hai": 2, "ba": 3, "bon": 4, "nam": 5, "vai": 3, "may": 3, "muoi": 10}


def duration_bucket(timing_text: str | None) -> str | None:
    """Map a reported timing expression to a coarse duration feature."""
    if not timing_text:
        return None
    folded = fold_aligned(timing_text)
    if re.search(r"sang nay|chieu nay|trua nay|toi qua|dem qua|hom nay|vua bi|moi bi|today|phut|tieng|gio", folded):
        if not re.search(r"\d+\s*(?:ngay|tuan|thang|nam)", folded):
            return "dur:hours"
    if re.search(r"hom qua|hom kia|yesterday", folded):
        return "dur:acute"
    if re.search(r"tuan truoc", folded):
        return "dur:subacute"
    if re.search(r"thang truoc|nam ngoai|lau roi|lau nay", folded):
        return "dur:chronic"
    match = re.search(
        r"(\d+(?:[.,]\d+)?|mot|hai|ba|bon|nam|vai|may|muoi)(?:\s*[-–]\s*\d+)?\s*(phut|tieng|gio|ngay|hom|bua|tuan|thang|nam|minute|hour|day|week|month|year)",
        folded,
    )
    if not match:
        return None
    raw, unit = match.groups()
    amount = _WORD_NUMBERS.get(raw)
    if amount is None:
        amount = float(raw.replace(",", "."))
    days = amount * _UNIT_DAYS[unit]
    if days < 1:
        return "dur:hours"
    if days <= 7:
        return "dur:acute"
    if days <= 28:
        return "dur:subacute"
    return "dur:chronic"


def max_temperature(text: str) -> float | None:
    values = []
    for found in re.finditer(r"(?<!\d)(3[5-9]|4[0-2])(?:[.,](\d))?\s*(?:do|°)", fold_aligned(text)):
        values.append(float(f"{found.group(1)}.{found.group(2) or 0}"))
    return max(values) if values else None

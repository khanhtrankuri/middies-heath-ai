"""Complaint profiles: which information a consultation needs per complaint.

Core slots must be known before the planner stops asking. Red-flag screens
list symptom keys whose explicit presence escalates care. ``emergency``
red flags route to the emergency response; ``urgent`` ones recommend same-day
in-person care. These tables are developer-authored for research use and
require clinician review before any real-world use.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    symptom_keys: tuple[str, ...]
    core_slots: tuple[str, ...]
    optional_slots: tuple[str, ...]
    emergency_flags: tuple[str, ...]
    urgent_flags: tuple[str, ...]
    red_flag_question: str
    location_needed_for: tuple[str, ...] = ()
    questions: dict[str, str] = field(default_factory=dict)


DEFAULT_QUESTIONS: dict[str, str] = {
    "timing": "Triệu chứng này bắt đầu từ khi nào và đã kéo dài bao lâu?",
    "location": "Bạn thấy khó chịu ở vị trí nào cụ thể?",
    "severity": "Nếu 0 là không đau/không khó chịu và 10 là nặng nhất, bạn tự đánh giá khoảng mấy điểm?",
    "character": "Bạn có thể mô tả cảm giác đó như thế nào không?",
    "progression": "Từ lúc bắt đầu đến giờ, triệu chứng tăng dần, giảm đi hay lúc có lúc không?",
    "triggers": "Có yếu tố nào làm triệu chứng nặng hơn hoặc đỡ hơn không?",
    "associated_symptoms": "Bạn có kèm theo triệu chứng nào khác không?",
    "relevant_history": "Bạn có bệnh lý nền nào (như tăng huyết áp, đái tháo đường, bệnh dạ dày, hen…) không?",
    "medications": "Bạn đã dùng thuốc gì cho triệu chứng này chưa?",
    "allergies": "Bạn có dị ứng với thuốc hoặc thức ăn nào không?",
    "age": "Người đang có triệu chứng bao nhiêu tuổi?",
}

PROFILES: tuple[Profile, ...] = (
    Profile(
        name="headache", label="Đau đầu", symptom_keys=("dau_dau",),
        core_slots=("timing", "location", "severity", "associated_symptoms", "red_flag_screen"),
        optional_slots=("character", "triggers", "progression", "relevant_history", "medications"),
        emergency_flags=("yeu_liet", "noi_kho", "co_giat", "ngat", "lo_mo"),
        urgent_flags=("cung_co",),
        red_flag_question=(
            "Bạn có cơn đau đầu dữ dội đột ngột, yếu hoặc tê một bên người, nói khó, "
            "méo miệng hay cứng cổ kèm sốt không?"
        ),
        location_needed_for=("dau_dau",),
        questions={
            "location": "Bạn đau ở vùng nào của đầu: một bên, hai bên, vùng trán hay sau gáy?",
            "character": "Cơn đau có cảm giác như thế nào: đau theo nhịp mạch, căng thắt như đeo vòng hay âm ỉ?",
            "severity": "Nếu 0 là không đau và 10 là đau nhất, cơn đau đầu của bạn khoảng mấy điểm?",
        },
    ),
    Profile(
        name="abdominal", label="Đau bụng / tiêu hóa",
        symptom_keys=("dau_bung", "tieu_chay", "non", "buon_non", "tao_bon", "o_chua", "day_hoi", "phan_mau"),
        core_slots=("timing", "location", "severity", "associated_symptoms", "red_flag_screen"),
        optional_slots=("character", "triggers", "progression", "relevant_history", "medications"),
        emergency_flags=("phan_mau", "ngat", "lo_mo"),
        urgent_flags=(),
        red_flag_question=(
            "Bạn có đau dữ dội không chịu nổi, bụng cứng, nôn ra máu, đi ngoài phân đen "
            "hoặc có máu không?"
        ),
        location_needed_for=("dau_bung",),
        questions={
            "location": "Bạn đau ở vị trí nào của bụng: vùng trên rốn, quanh rốn, bụng dưới bên phải hay bên trái?",
            "character": "Cơn đau có cảm giác như thế nào: âm ỉ, quặn từng cơn hay nóng rát?",
            "severity": "Nếu 0 là không đau và 10 là đau nhất, cơn đau bụng của bạn khoảng mấy điểm?",
            "triggers": "Cơn đau có liên quan đến bữa ăn không, ví dụ nặng hơn sau ăn hay khi đói?",
        },
    ),
    Profile(
        name="respiratory", label="Hô hấp / tai mũi họng",
        symptom_keys=("ho", "dau_hong", "so_mui", "nghet_mui", "hat_hoi", "khan_tieng", "kho_khe"),
        core_slots=("timing", "associated_symptoms", "red_flag_screen"),
        optional_slots=("character", "severity", "relevant_history", "medications"),
        emergency_flags=("kho_tho", "dau_nguc", "lo_mo"),
        urgent_flags=("kho_khe",),
        red_flag_question="Bạn có khó thở, đau ngực, thở khò khè, môi tím hoặc ho ra máu không?",
        questions={
            "character": "Bạn ho khan hay ho có đờm? Nếu có đờm thì đờm màu gì?",
            "severity": "Bạn có sốt không, nếu có thì nhiệt độ cao nhất khoảng bao nhiêu độ?",
        },
    ),
    Profile(
        name="fever", label="Sốt", symptom_keys=("sot",),
        core_slots=("timing", "severity", "associated_symptoms", "red_flag_screen"),
        optional_slots=("progression", "triggers", "relevant_history", "medications"),
        emergency_flags=("co_giat", "lo_mo", "kho_tho", "ngat"),
        urgent_flags=("cung_co", "chay_mau"),
        red_flag_question=(
            "Bạn có cứng cổ, lơ mơ, khó thở, co giật, chảy máu cam/chân răng "
            "hoặc nổi chấm xuất huyết dưới da không?"
        ),
        questions={
            "severity": "Bạn đã đo nhiệt độ chưa, sốt cao nhất khoảng bao nhiêu độ?",
            "triggers": "Gần đây bạn có bị muỗi đốt, ăn đồ lạ hoặc tiếp xúc với người đang bị sốt không?",
        },
    ),
    Profile(
        name="urinary", label="Tiết niệu", symptom_keys=("tieu_buot", "tieu_mau"),
        core_slots=("timing", "associated_symptoms", "red_flag_screen"),
        optional_slots=("relevant_history", "medications"),
        emergency_flags=("lo_mo",),
        urgent_flags=("dau_hong_lung",),
        red_flag_question=(
            "Bạn có sốt cao, rét run, đau nhiều vùng hông lưng, buồn nôn hoặc đang mang thai không?"
        ),
    ),
    Profile(
        name="skin", label="Da liễu", symptom_keys=("phat_ban", "me_day", "ngua"),
        core_slots=("timing", "location", "triggers", "red_flag_screen"),
        optional_slots=("associated_symptoms", "relevant_history", "medications"),
        emergency_flags=("kho_tho",),
        urgent_flags=("sot",),
        red_flag_question="Bạn có sưng môi, sưng mặt, khó thở hoặc chóng mặt kèm theo không?",
        location_needed_for=("phat_ban", "me_day", "ngua"),
        questions={
            "location": "Ban hoặc ngứa xuất hiện ở vùng nào trên cơ thể?",
            "triggers": "Trước khi bị, bạn có ăn đồ lạ, dùng thuốc mới, mỹ phẩm hay tiếp xúc hóa chất không?",
        },
    ),
    Profile(
        name="musculoskeletal", label="Cơ xương khớp", symptom_keys=("dau_lung", "dau_khop", "dau_co"),
        core_slots=("timing", "location", "severity", "triggers", "red_flag_screen"),
        optional_slots=("character", "progression", "relevant_history", "medications"),
        emergency_flags=("yeu_liet",),
        urgent_flags=("sot", "te_bi"),
        red_flag_question=(
            "Bạn có tê yếu chân tay, khó kiểm soát tiểu tiện/đại tiện, sốt hoặc vừa bị chấn thương mạnh không?"
        ),
        location_needed_for=("dau_lung", "dau_khop", "dau_co"),
        questions={
            "location": "Bạn đau ở vị trí nào, cơn đau có lan đi đâu không?",
            "triggers": "Cơn đau có xuất hiện sau khi mang vác, vận động mạnh hoặc chấn thương không?",
        },
    ),
    Profile(
        name="dizziness", label="Chóng mặt", symptom_keys=("chong_mat",),
        core_slots=("timing", "triggers", "associated_symptoms", "red_flag_screen"),
        optional_slots=("character", "relevant_history", "medications"),
        emergency_flags=("yeu_liet", "noi_kho", "ngat", "dau_nguc"),
        urgent_flags=(),
        red_flag_question="Bạn có yếu hoặc tê một bên người, nói khó, nhìn đôi, ngất hay đau ngực kèm theo không?",
        questions={
            "triggers": "Chóng mặt có xuất hiện khi thay đổi tư thế như xoay đầu, nằm xuống hay đứng dậy không?",
            "character": "Bạn thấy mọi thứ quay cuồng hay chỉ choáng váng, xây xẩm?",
        },
    ),
    Profile(
        name="general", label="Chung", symptom_keys=(),
        core_slots=("timing", "severity", "associated_symptoms"),
        optional_slots=("relevant_history", "medications", "allergies"),
        emergency_flags=(),
        urgent_flags=(),
        red_flag_question="Bạn có khó thở, đau ngực, ngất hoặc yếu liệt kèm theo không?",
    ),
)
PROFILE_BY_NAME = {profile.name: profile for profile in PROFILES}


def profile_for(symptom_keys: list[str]) -> Profile:
    """Pick the profile of the earliest reported symptom that has one."""
    for key in symptom_keys:
        for profile in PROFILES:
            if key in profile.symptom_keys:
                return profile
    return PROFILE_BY_NAME["general"]


def required_slots(profile: Profile, symptom_keys: set[str]) -> tuple[str, ...]:
    """Core slots; location is required only for complaints that have one."""
    if profile.location_needed_for and not symptom_keys.intersection(profile.location_needed_for):
        return tuple(slot for slot in profile.core_slots if slot != "location")
    return profile.core_slots


def question_template(profile: Profile, slot: str) -> str:
    if slot == "red_flag_screen":
        return profile.red_flag_question
    return profile.questions.get(slot) or DEFAULT_QUESTIONS[slot]

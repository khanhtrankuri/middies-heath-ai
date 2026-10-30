"""Reference knowledge base for related-condition hypotheses.

Each condition lists feature tokens (see ``features.py``) that *support* it,
with integer-like relevance weights. Weights encode how characteristic a
finding is in common teaching material; they are NOT probabilities, are not
calibrated, and must never be displayed as likelihoods.

A condition is excluded when the user reports an ``excludes`` feature, or
explicitly denies (``neg:``) a symptom whose support weight is at least
``KEY_FEATURE_WEIGHT``.

STATUS: developer-authored for research and UI prototyping. It has not been
reviewed by a clinician and is not a diagnostic reference.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Urgency = Literal["routine", "soon", "urgent"]
KEY_FEATURE_WEIGHT = 1.5
KB_VERSION = "kb-v1-unreviewed"


@dataclass(frozen=True)
class Condition:
    name: str
    profiles: tuple[str, ...]
    supports: dict[str, float]
    urgency: Urgency
    note: str
    excludes: tuple[str, ...] = ()

    def excluded_by(self, features: set[str]) -> bool:
        if features.intersection(self.excludes):
            return True
        return any(
            token.startswith("sym:") and weight >= KEY_FEATURE_WEIGHT and f"neg:{token[4:]}" in features
            for token, weight in self.supports.items()
        )

    def score(self, features: set[str]) -> float:
        return sum(weight for token, weight in self.supports.items() if token in features)


CONDITIONS: tuple[Condition, ...] = (
    # Headache
    Condition("Đau đầu do căng thẳng", ("headache",), {
        "loc:hai_ben_dau": 1.0, "char:that_chat": 1.0, "trig:cang_thang": 1.0, "prog:tai_phat": 0.5,
        "neg:buon_non": 0.5, "neg:so_anh_sang": 0.5, "sym:dau_dau": 0.5,
    }, "routine", "Thường liên quan căng thẳng, thiếu ngủ, tư thế làm việc.", excludes=("sym:sot_cao",)),
    Condition("Đau nửa đầu (migraine)", ("headache",), {
        "loc:mot_ben_dau": 1.0, "char:theo_nhip": 1.0, "sym:buon_non": 1.0, "sym:non": 0.5,
        "sym:so_anh_sang": 1.0, "prog:tai_phat": 0.5, "sym:dau_dau": 0.5,
    }, "routine", "Thường tái diễn thành cơn; cần khám nếu lần đầu xuất hiện hoặc thay đổi tính chất.",
        excludes=("sym:sot_cao",)),
    Condition("Viêm xoang", ("headache", "respiratory"), {
        "loc:tran_mat": 1.0, "sym:nghet_mui": 1.0, "sym:so_mui": 0.7, "sym:sot": 0.5, "sym:dau_dau": 0.5,
    }, "routine", "Thường đi kèm nghẹt mũi, chảy dịch mũi, đau vùng mặt."),
    Condition("Đau đầu trong bệnh cảnh nhiễm virus/cúm", ("headache", "fever"), {
        "sym:sot": 1.0, "sym:dau_co": 1.0, "sym:dau_hong": 0.7, "sym:so_mui": 0.5, "sym:ho": 0.5,
        "dur:acute": 0.3, "sym:dau_dau": 0.5,
    }, "routine", "Đau đầu có thể là một phần của bệnh cảnh sốt do virus."),
    # Abdominal
    Condition("Viêm dạ dày / khó tiêu chức năng", ("abdominal",), {
        "loc:thuong_vi": 1.0, "char:nong_rat": 1.0, "trig:khi_doi": 0.8, "trig:sau_an": 0.6, "sym:o_chua": 0.8,
        "sym:day_hoi": 0.6, "hist:da_day": 0.6, "prog:tai_phat": 0.4,
    }, "routine", "Cần khám nếu đau kéo dài, sụt cân, nôn ra máu hoặc đi ngoài phân đen."),
    Condition("Viêm dạ dày ruột cấp / ngộ độc thực phẩm", ("abdominal", "fever"), {
        "sym:tieu_chay": 1.0, "sym:non": 1.0, "sym:buon_non": 0.5, "char:quan": 0.6, "loc:quanh_ron": 0.4,
        "loc:lan_toa_bung": 0.4, "trig:an_la": 1.0, "expo:nguoi_benh": 0.7, "sym:sot": 0.4,
        "dur:hours": 0.3, "dur:acute": 0.3,
    }, "soon", "Nguy cơ chính là mất nước; cần khám sớm nếu nôn/tiêu chảy nhiều, sốt cao hoặc có máu."),
    Condition("Viêm ruột thừa (cần loại trừ)", ("abdominal",), {
        "loc:ho_chau_phai": 1.5, "prog:di_chuyen": 1.2, "prog:tang_dan": 0.6, "sym:sot": 0.5,
        "sym:buon_non": 0.4, "sym:non": 0.4, "dur:hours": 0.3, "dur:acute": 0.3,
    }, "urgent", "Đau bụng dưới bên phải tăng dần cần được bác sĩ thăm khám trực tiếp sớm.",
        excludes=("dur:chronic", "prog:tai_phat")),
    Condition("Cơn đau quặn mật / viêm túi mật", ("abdominal",), {
        "loc:ha_suon_phai": 1.5, "trig:an_dau_mo": 1.0, "char:quan": 0.5, "sym:sot": 0.4,
        "sym:buon_non": 0.4, "hist:soi": 0.7,
    }, "soon", "Cần khám nếu đau dưới sườn phải kéo dài, kèm sốt hoặc vàng da."),
    Condition("Hội chứng ruột kích thích / táo bón chức năng", ("abdominal",), {
        "loc:bung_duoi": 0.5, "sym:tao_bon": 1.0, "sym:tieu_chay": 0.3, "sym:day_hoi": 0.6,
        "prog:tai_phat": 1.0, "dur:chronic": 1.0, "trig:cang_thang": 0.5,
    }, "routine", "Chỉ nghĩ đến sau khi đã loại trừ nguyên nhân thực thể.",
        excludes=("sym:sot", "sym:sut_can", "sym:phan_mau")),
    # Respiratory
    Condition("Cảm lạnh (nhiễm virus đường hô hấp trên)", ("respiratory", "fever"), {
        "sym:so_mui": 1.0, "sym:nghet_mui": 0.8, "sym:hat_hoi": 0.7, "sym:dau_hong": 0.7, "sym:ho": 0.4,
        "sym:sot": 0.2, "dur:acute": 0.5,
    }, "routine", "Thường tự cải thiện trong khoảng 7–10 ngày.", excludes=("sym:sot_cao",)),
    Condition("Cúm", ("respiratory", "fever"), {
        "sym:sot": 1.0, "sym:sot_cao": 0.8, "sym:dau_co": 1.0, "sym:met_moi": 0.6, "sym:dau_dau": 0.5,
        "sym:ho": 0.5, "onset:sudden": 0.6, "expo:nguoi_benh": 0.5,
    }, "routine", "Người cao tuổi, phụ nữ mang thai, người có bệnh nền nên đi khám sớm."),
    Condition("Viêm họng cấp", ("respiratory", "fever"), {
        "sym:dau_hong": 1.5, "sym:kho_nuot": 1.0, "sym:sot": 0.6, "neg:ho": 0.4, "loc:co_hong": 0.4,
    }, "routine", "Cần khám nếu sốt cao, khó nuốt nhiều hoặc không cải thiện sau vài ngày."),
    Condition("Viêm phế quản cấp", ("respiratory",), {
        "sym:ho": 1.0, "char:ho_dom": 1.0, "char:dom_mu": 0.3, "dur:acute": 0.3, "dur:subacute": 0.6,
        "sym:sot": 0.3, "sym:kho_khe": 0.3,
    }, "routine", "Cần khám nếu ho kéo dài trên 3 tuần, sốt cao hoặc khó thở."),
    Condition("Viêm mũi dị ứng", ("respiratory",), {
        "sym:hat_hoi": 1.0, "sym:so_mui": 0.8, "sym:nghet_mui": 0.6, "hist:di_ung": 1.0, "prog:tai_phat": 0.8,
        "trig:tiep_xuc": 0.7, "trig:thoi_tiet": 0.6, "neg:sot": 0.5,
    }, "routine", "Thường tái diễn theo mùa hoặc khi tiếp xúc dị nguyên.", excludes=("sym:sot",)),
    Condition("Hen phế quản", ("respiratory",), {
        "sym:kho_khe": 1.5, "hist:hen": 1.5, "char:ho_khan": 0.4, "trig:thoi_tiet": 0.4, "trig:tiep_xuc": 0.4,
        "prog:tai_phat": 0.5,
    }, "soon", "Khó thở tăng dần hoặc nói không thành câu là tình trạng cấp cứu."),
    Condition("Ho do trào ngược dạ dày thực quản", ("respiratory", "abdominal"), {
        "sym:o_chua": 1.2, "char:ho_khan": 0.5, "trig:sau_an": 0.6, "dur:chronic": 0.6, "hist:da_day": 0.6,
    }, "routine", "Ho thường nặng hơn sau ăn hoặc khi nằm."),
    # Fever
    Condition("Sốt do nhiễm virus", ("fever",), {
        "sym:sot": 1.0, "sym:met_moi": 0.5, "sym:dau_co": 0.5, "sym:so_mui": 0.5, "sym:ho": 0.4,
        "sym:dau_hong": 0.4, "dur:acute": 0.5,
    }, "routine", "Cần khám nếu sốt trên 3 ngày, sốt cao khó hạ hoặc có dấu hiệu nguy hiểm."),
    Condition("Sốt xuất huyết Dengue (cần loại trừ)", ("fever",), {
        "sym:sot_cao": 1.2, "sym:sot": 0.5, "sym:dau_dau": 0.6, "loc:tran_mat": 0.5, "sym:dau_co": 0.8,
        "sym:phat_ban": 0.7, "sym:chay_mau": 1.0, "expo:muoi": 1.0, "dur:acute": 0.4,
        "neg:so_mui": 0.3, "neg:ho": 0.3,
    }, "soon", "Ở vùng lưu hành, sốt cao cần được khám và xét nghiệm máu theo chỉ định của bác sĩ."),
    # Urinary
    Condition("Viêm bàng quang (nhiễm khuẩn tiết niệu dưới)", ("urinary", "abdominal"), {
        "sym:tieu_buot": 1.5, "loc:bung_duoi": 0.8, "sym:tieu_mau": 0.5, "neg:sot": 0.5, "neg:dau_hong_lung": 0.4,
    }, "soon", "Nên khám và xét nghiệm nước tiểu; đi khám ngay nếu sốt hoặc đau hông lưng.",
        excludes=("sym:sot_cao",)),
    Condition("Viêm thận bể thận (cần loại trừ)", ("urinary", "fever"), {
        "sym:sot": 1.0, "sym:sot_cao": 0.6, "sym:dau_hong_lung": 1.5, "loc:hong_lung": 1.0,
        "sym:tieu_buot": 0.6, "sym:buon_non": 0.4, "sym:non": 0.4,
    }, "urgent", "Sốt kèm đau hông lưng và tiểu buốt cần được khám trong ngày."),
    Condition("Sỏi tiết niệu", ("urinary", "abdominal"), {
        "loc:hong_lung": 1.0, "sym:dau_hong_lung": 1.0, "char:quan": 1.0, "sym:tieu_mau": 0.8,
        "prog:tung_con": 0.6, "hist:soi": 1.0, "neg:sot": 0.3,
    }, "soon", "Đau quặn hông lưng kèm sốt hoặc bí tiểu cần đi khám ngay."),
    # Skin
    Condition("Viêm da tiếp xúc", ("skin",), {
        "trig:tiep_xuc": 1.5, "sym:ngua": 0.6, "sym:phat_ban": 0.6, "loc:tay_chan": 0.3,
    }, "routine", "Tránh tác nhân nghi ngờ; khám nếu lan rộng, chảy dịch hoặc không cải thiện."),
    Condition("Mày đay cấp", ("skin",), {
        "sym:me_day": 1.5, "sym:ngua": 0.8, "trig:an_la": 0.6, "trig:tiep_xuc": 0.3, "prog:tung_con": 0.3,
        "hist:di_ung": 0.6,
    }, "routine", "Sưng môi/lưỡi hoặc khó thở kèm theo là dấu hiệu phản vệ cần cấp cứu."),
    Condition("Viêm da cơ địa (chàm)", ("skin",), {
        "hist:di_ung": 1.0, "prog:tai_phat": 1.0, "sym:ngua": 1.0, "dur:chronic": 0.7,
    }, "routine", "Thường tái diễn, liên quan cơ địa dị ứng."),
    Condition("Phát ban trong bệnh cảnh nhiễm virus", ("skin", "fever"), {
        "sym:sot": 1.0, "sym:phat_ban": 1.0, "expo:nguoi_benh": 0.5, "dur:acute": 0.3,
    }, "soon", "Sốt kèm phát ban nên được khám để loại trừ nguyên nhân cần theo dõi đặc biệt."),
    # Musculoskeletal
    Condition("Căng cơ / bong gân", ("musculoskeletal",), {
        "trig:van_dong": 1.5, "dur:acute": 0.5, "loc:lung_duoi": 0.4, "neg:te_bi": 0.4, "sym:sung": 0.3,
    }, "routine", "Khám nếu không đi lại/cử động được, biến dạng hoặc đau tăng dần."),
    Condition("Thoát vị đĩa đệm / chèn ép rễ thần kinh", ("musculoskeletal",), {
        "loc:lan_xuong_chan": 1.5, "sym:te_bi": 1.0, "char:te_lan": 1.0, "loc:lung_duoi": 0.6,
        "trig:van_dong": 0.4, "prog:tai_phat": 0.4,
    }, "soon", "Yếu chân hoặc rối loạn tiểu tiện cần đi khám ngay."),
    Condition("Thoái hóa khớp", ("musculoskeletal",), {
        "sym:dau_khop": 1.0, "dur:chronic": 1.0, "prog:tai_phat": 0.6, "trig:van_dong": 0.5,
    }, "routine", "Thường gặp ở người lớn tuổi, đau tăng khi vận động."),
    Condition("Viêm khớp (gout hoặc viêm khớp khác)", ("musculoskeletal",), {
        "sym:sung": 1.0, "sym:dau_khop": 0.8, "onset:sudden": 0.6, "sym:sot": 0.3,
    }, "soon", "Khớp sưng nóng đỏ, nhất là kèm sốt, cần được khám sớm."),
    # Dizziness
    Condition("Chóng mặt tư thế kịch phát lành tính", ("dizziness",), {
        "trig:tu_the": 1.5, "char:quay_cuong": 1.0, "prog:tung_con": 0.6,
    }, "routine", "Thường xuất hiện từng cơn ngắn khi xoay đầu hoặc thay đổi tư thế."),
    Condition("Rối loạn tiền đình / viêm thần kinh tiền đình", ("dizziness",), {
        "char:quay_cuong": 1.0, "sym:buon_non": 0.8, "sym:non": 0.6, "onset:sudden": 0.5,
    }, "soon", "Chóng mặt kéo dài kèm nôn nên được khám để loại trừ nguyên nhân thần kinh trung ương."),
    Condition("Hạ huyết áp tư thế / mất nước", ("dizziness",), {
        "trig:tu_the": 0.6, "sym:tieu_chay": 0.6, "sym:non": 0.5, "sym:met_moi": 0.4,
    }, "routine", "Uống đủ nước; khám nếu ngất hoặc tái diễn nhiều."),
    Condition("Thiếu máu (cần xét nghiệm)", ("dizziness", "general"), {
        "sym:met_moi": 1.0, "sym:hoi_hop": 0.6, "dur:chronic": 0.5, "sym:chong_mat": 0.5,
    }, "soon", "Mệt và chóng mặt kéo dài nên được khám và xét nghiệm máu."),
)


def candidates_for(profile: str, features: set[str]) -> list[Condition]:
    return [
        condition for condition in CONDITIONS
        if profile in condition.profiles and not condition.excluded_by(features)
    ]

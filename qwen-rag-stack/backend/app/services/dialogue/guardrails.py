"""Medical-domain scope and prompt-injection guardrails.

These rules run after emergency detection (an emergency is never refused)
and before any model call. They are deliberately conservative about refusing:
a message with any health cue stays in scope.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel

from .lexicon import SYMPTOMS, find_term, fold_aligned

ScopeCategory = Literal["medical", "greeting", "unclear", "out_of_scope", "prompt_injection"]

INJECTION_PATTERNS = (
    r"bo qua (?:moi|cac|tat ca|het|nhung)? ?(?:quy tac|huong dan|chi dan|chi thi|lenh|rang buoc|gioi han)",
    r"quen (?:het |di )?(?:cac |moi )?(?:quy tac|huong dan|chi dan)",
    r"ignore (?:all |any |the )?(?:previous |prior |above )?(?:instructions|rules|prompts?)",
    r"disregard (?:all |the )?(?:previous |above )?(?:instructions|rules)",
    r"(?:system|developer) prompt|prompt he thong|tiet lo (?:prompt|huong dan|chi dan|cau hinh)",
    r"you are now|tu bay gio ban (?:la|se dong vai)|hay dong vai|dong vai (?:la )?(?!benh nhan)|act as (?:a|an)\b|pretend (?:to be|you are)",
    r"developer mode|jailbreak|\bdan mode\b|che do (?:nha phat trien|khong gioi han)",
    r"<\|im_start\|>|<\|im_end\|>|\[/?inst\]|<\|system\|>",
)
MEDICAL_CUES = (
    r"benh|thuoc|bac si|y te|suc khoe|trieu chung|kham|benh vien|phong kham|cap cuu|tiem|vac-?xin|vaccine",
    r"chan doan|xet nghiem|dieu tri|dinh duong|an kieng|huyet ap|duong huyet|cholesterol|mang thai|kinh nguyet",
    r"tre so sinh|da lieu|nha khoa|sau rang|viem \w+|nhiem (?:trung|khuan|virus)|ung thu|di ung|cam cum|tiem chung",
    r"health|doctor|medicine|symptom|disease|pain|fever|cough|hospital",
)
NON_MEDICAL_CUES = (
    r"viet (?:code|chuong trinh|ham|tho|bai van|bai hat|truyen|email)|lap trinh|python|javascript|sql|html",
    r"giai (?:bai toan|phuong trinh|he phuong trinh)|tinh (?:tich phan|dao ham)",
    r"thoi tiet|bong da|tran dau|ty so|chung khoan|co phieu|bitcoin|tien ao|ty gia|gia vang",
    r"cong thuc nau|nau mon|du lich|dat ve|khach san|chinh tri|bau cu|loi bai hat|ke chuyen|truyen cuoi",
    r"dich (?:sang|cau|doan)|translate|write (?:a |an )?(?:poem|story|essay|code|email)|tro choi|choi game|phim hay",
    r"what(?:'s| is) the capital|thu do cua|ai la tong thong|lich su viet nam",
)
GREETING = r"^(?:xin chao|chao(?: ban| bac si| em| anh| chi)?|hello|hi|alo|cam on|thanks?)(?: ban| bac si| a)?[!. ]*$"

REFUSAL_OUT_OF_SCOPE = (
    "Xin lỗi, tôi chỉ hỗ trợ các câu hỏi về triệu chứng, sức khỏe và phòng bệnh. "
    "Nếu bạn đang có triệu chứng hoặc thắc mắc về sức khỏe, hãy mô tả để tôi hỗ trợ."
)
REFUSAL_INJECTION = (
    "Tôi không thể thay đổi vai trò, bỏ qua quy tắc an toàn hoặc tiết lộ cấu hình hệ thống. "
    "Tôi vẫn có thể hỗ trợ thông tin sức khỏe: bạn đang gặp triệu chứng gì?"
)


class ScopeDecision(BaseModel):
    category: ScopeCategory
    in_scope: bool
    reply: str | None = None


def _has(patterns: tuple[str, ...], folded: str) -> bool:
    return any(re.search(rf"(?<!\w)(?:{pattern})(?!\w)", folded) for pattern in patterns)


def check_scope(text: str) -> ScopeDecision:
    folded = fold_aligned(text).strip()
    if _has(INJECTION_PATTERNS, folded) or re.search(r"<\|im_(?:start|end)\|>", text):
        return ScopeDecision(category="prompt_injection", in_scope=False, reply=REFUSAL_INJECTION)
    if re.match(GREETING, folded):
        return ScopeDecision(category="greeting", in_scope=True)
    medical = _has(MEDICAL_CUES, folded) or any(find_term(text, term) for term in SYMPTOMS)
    if medical:
        return ScopeDecision(category="medical", in_scope=True)
    if _has(NON_MEDICAL_CUES, folded):
        return ScopeDecision(category="out_of_scope", in_scope=False, reply=REFUSAL_OUT_OF_SCOPE)
    return ScopeDecision(category="unclear", in_scope=True)

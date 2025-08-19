########################################
# utils/style.py (공유)
########################################
from typing import List, Optional

MBTI_TRAIT_MAP = {
    "INTJ": ["계획적", "독립적", "분석적"],
    "INTP": ["호기심", "이론적", "유연한 사고"],
    "ENTJ": ["리더십", "결단력", "목표지향"],
    "ENTP": ["아이디어", "도전적", "순발력"],
    "INFJ": ["배려", "통찰", "가치중심"],
    "INFP": ["따뜻함", "이상주의", "공감"],
    "ENFJ": ["조화", "사교성", "조력자"],
    "ENFP": ["즉흥", "열정", "상상력"],
    "ISTJ": ["책임감", "성실", "체계"],
    "ISFJ": ["헌신", "세심", "배려"],
    "ESTJ": ["실용", "조직적", "원칙"],
    "ESFJ": ["친화", "협력", "배려"],
    "ISTP": ["문제해결", "냉정", "실험정신"],
    "ISFP": ["온화", "감성", "자유로움"],
    "ESTP": ["액티브", "현실적", "순간집중"],
    "ESFP": ["유쾌", "에너지", "사교"],
}

def style_tokens(age: Optional[int], gender: Optional[str], nationality: Optional[str]) -> List[str]:
    out: List[str] = []
    if age is not None:
        if age <= 26:
            out += ["GenZ", "밈", "짧고임팩트"]
        elif age <= 40:
            out += ["MZ", "트렌디", "현대적"]
        else:
            out += ["차분", "정제", "품위"]
    if gender and gender != "unknown":
        out.append(gender)
    if nationality:
        out.append(nationality)
    return out
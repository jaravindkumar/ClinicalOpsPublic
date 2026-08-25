from __future__ import annotations
import re

from typing import Dict, List


def parse_cohort_request(text: str) -> Dict[str, object]:
    """Parse plain-language cohort intent into the criteria supported by Cohort Builder.

    The parser is deliberately transparent: it extracts demographics, encounter recency,
    inclusion diagnoses and exclusion diagnoses. It does not invent unsupported criteria.
    """
    raw=(text or "").strip(); q=raw.lower().replace("–","-").replace("—","-")
    draft: Dict[str, object] = {"name":"","any_age":True,"age":(0,120),"sex":"Any","recent":"Any time",
        "include_keywords":[],"exclude_keywords":[],"include_logic":"AND","exclude_logic":"OR","unparsed":[]}

    # Age: 50-70, 50 to 70, between 50 and 70, aged 50 and 70.
    pats=[r"(?:age|aged|ages?)\s*(?:between\s*)?(\d{1,3})\s*(?:-|to|and)\s*(\d{1,3})",
          r"between\s*(?:ages?\s*)?(\d{1,3})\s*(?:and|to|-)\s*(\d{1,3})",
          r"\b(\d{2,3})\s*(?:-|to)\s*(\d{2,3})\b"]
    m=next((re.search(p,q) for p in pats if re.search(p,q)),None)
    if m:
        lo,hi=sorted(map(int,m.groups())); draft['any_age']=False; draft['age']=(max(0,lo),min(120,hi))
    else:
        m=re.search(r"(?:age[d]?\s*)?(?:over|older than|at least|>=)\s*(\d{1,3})",q)
        if m: draft['any_age']=False; draft['age']=(int(m.group(1)),120)
        m2=re.search(r"(?:age[d]?\s*)?(?:under|younger than|at most|<=)\s*(\d{1,3})",q)
        if m2: draft['any_age']=False; draft['age']=(0,int(m2.group(1)))

    if re.search(r"\b(female|women|woman|females)\b",q): draft['sex']='Female'
    elif re.search(r"\b(male|men|man|males)\b",q): draft['sex']='Male'

    if re.search(r"(past|last|within)\s*(12\s*months?|1\s*year)|encounter.*(?:12\s*months?|1\s*year)",q): draft['recent']='≤ 1 year'
    elif re.search(r"(past|last|within)\s*3\s*years?|encounter.*3\s*years?",q): draft['recent']='≤ 3 years'
    elif re.search(r"(past|last|within)\s*5\s*years?|encounter.*5\s*years?",q): draft['recent']='≤ 5 years'
    elif re.search(r"(past|last|within)\s*10\s*years?|encounter.*10\s*years?",q): draft['recent']='≤ 10 years'

    concepts={
      'diabetes':['diabetes','diabetic','t2dm','type 2 diabetes','type ii diabetes'],
      'hypertension':['hypertension','hypertensive','high blood pressure'],
      'asthma':['asthma','asthmatic'], 'copd':['copd','chronic obstructive pulmonary'],
      'heart failure':['heart failure','congestive heart failure','chf'],
      'chronic kidney disease':['chronic kidney disease','kidney disease','renal disease','ckd'],
      'obesity':['obesity','obese'], 'depression':['depression','depressive'],
      'pregnancy':['pregnancy','pregnant'], 'stroke':['stroke','cerebrovascular accident','cva'],
      'myocardial infarction':['myocardial infarction','heart attack','acute mi'],
      'coronary artery disease':['coronary artery disease','coronary heart disease','cad'],
      'hyperlipidemia':['hyperlipidemia','hyperlipidaemia','high cholesterol'],
      'atrial fibrillation':['atrial fibrillation','afib','a-fib'],
      'cancer':['cancer','malignancy','malignant neoplasm'],
      'anemia':['anemia','anaemia'], 'osteoporosis':['osteoporosis'],
      'arthritis':['arthritis'], 'dementia':['dementia','alzheimer'],
    }
    exclude_spans=[]
    for marker in ['excluding','exclude','without','except for','except']:
        for mm in re.finditer(r'\b'+re.escape(marker)+r'\b',q): exclude_spans.append(mm.start())
    inc=[]; exc=[]
    for canonical,aliases in concepts.items():
        hits=[]
        for alias in aliases:
            hits += [m.start() for m in re.finditer(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',q)]
        for pos in hits:
            # Exclusion applies when an exclusion marker occurs in the preceding clause.
            prior=[x for x in exclude_spans if x < pos]
            boundary=max(q.rfind(',',0,pos),q.rfind(';',0,pos),q.rfind('.',0,pos))
            is_exc=bool(prior and max(prior) >= boundary)
            (exc if is_exc else inc).append(canonical)
            break
    # Remove excluded concepts from inclusion if they were mentioned twice/ambiguously.
    exc=list(dict.fromkeys(exc)); inc=[x for x in dict.fromkeys(inc) if x not in exc]
    draft['include_keywords']=inc; draft['exclude_keywords']=exc
    return draft


def parse_recency_days(text: str):
    """Return a day-based encounter window when explicitly stated."""
    s = str(text or "").lower()
    m = re.search(r"(?:within(?: the)? last|in the last|past|last)\s+(\d+)\s*days?", s)
    if m:
        return int(m.group(1))
    return None

# ---- v2.7 deterministic semantic enrichment ----
def _v27_age_range(text: str):
    s=str(text or "").lower().replace("–","-").replace("—","-")
    patterns=[
        r"\b(?:aged?|ages?)\s*(\d{1,3})\s*(?:to|-)\s*(\d{1,3})\b",
        r"\bbetween\s+(\d{1,3})\s+and\s+(\d{1,3})\b",
        r"\b(\d{1,3})\s*-\s*(\d{1,3})\s*(?:year|yr)[ -]?olds?\b",
        r"\badults?\s+(\d{1,3})\s*-\s*(\d{1,3})\b",
    ]
    for pat in patterns:
        m=re.search(pat,s)
        if m:
            lo,hi=int(m.group(1)),int(m.group(2))
            if 0 <= lo <= hi <= 120: return lo,hi
    return None

def _v27_hba1c(text: str):
    s=str(text or "").lower()
    # Only interpret a number when explicitly attached to HbA1c language.
    m=re.search(r"(?:hba1c|hb\s*a1c)[^0-9<>]{0,24}(>=|<=|>|<|=)\s*(\d+(?:\.\d+)?)",s)
    if m: return m.group(1),float(m.group(2))
    verbal=[
      (r"(?:hba1c|hb\s*a1c)[^0-9]{0,24}(?:at least|minimum(?: of)?|no less than)\s*(\d+(?:\.\d+)?)",">="),
      (r"(?:hba1c|hb\s*a1c)[^0-9]{0,24}(\d+(?:\.\d+)?)\s*(?:or higher|or above|and above)",">="),
      (r"(?:hba1c|hb\s*a1c)[^0-9]{0,24}(?:at most|maximum(?: of)?|no more than)\s*(\d+(?:\.\d+)?)","<="),
      (r"(?:hba1c|hb\s*a1c)[^0-9]{0,24}(\d+(?:\.\d+)?)\s*(?:or lower|or below|and below)","<="),
      (r"(?:hba1c|hb\s*a1c)[^0-9]{0,24}(?:above|over|greater than)\s*(\d+(?:\.\d+)?)",">"),
      (r"(?:hba1c|hb\s*a1c)[^0-9]{0,24}(?:below|under|less than)\s*(\d+(?:\.\d+)?)","<"),
    ]
    for pat,op in verbal:
        m=re.search(pat,s)
        if m:return op,float(m.group(1))
    return None

def _v27_ckd_exclusion(text: str):
    s=str(text or "").lower()
    ckd=r"(?:ckd|chronic kidney disease)"
    return bool(re.search(rf"(?:exclude|excluding|without|but\s+no|no)\s+{ckd}",s))

_parse_cohort_request_pre_v27 = parse_cohort_request

def parse_cohort_request(text: str):
    draft=_parse_cohort_request_pre_v27(text) or {}
    age=_v27_age_range(text)
    if age:
        draft["age_min"],draft["age_max"]=age
    obs=_v27_hba1c(text)
    if obs:
        draft["observation_description"]="Hemoglobin A1c/Hemoglobin.total in Blood"
        draft["observation_operator"],draft["observation_value"]=obs
    days=parse_recency_days(text)
    if days is not None:
        draft["recent_days"]=days
    if _v27_ckd_exclusion(text):
        existing=list(draft.get("exclude_keywords") or draft.get("exclude_conditions") or [])
        if not any(("ckd" in str(x).lower() or "chronic kidney" in str(x).lower()) for x in existing):
            existing.append("Chronic kidney disease")
        draft["exclude_keywords"]=existing
    return draft

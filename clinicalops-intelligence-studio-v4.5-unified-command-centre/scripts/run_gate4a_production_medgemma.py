#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse,json,time,sys,requests
from dataclasses import asdict, is_dataclass
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.medgemma_client import extract, DEFAULT_OLLAMA_MODEL

CASES=[
{"id":"X01","class":"complete","text":"62-year-old patient reports persistent fatigue and polyuria. History: type 2 diabetes mellitus and essential hypertension. HbA1c 8.1%. Creatinine normal. No chest pain, dyspnoea or neurological deficit.","must":["fatigue","polyuria"],"forbid":["chest pain","dyspnoea"]},
{"id":"X02","class":"red_flag","text":"Patient reports new crushing central chest pain radiating to the left arm with diaphoresis. ECG ordered; troponin result is pending.","must":["chest pain","troponin"],"forbid":[]},
{"id":"X03","class":"missing_result","text":"Persistent cough and fever. Chest X-ray was ordered yesterday but no result is documented in the record.","must":["cough","fever","chest"],"forbid":[]},
{"id":"X04","class":"conflict","text":"Same-day HbA1c entries conflict: one result is 5.8% and another is 10.2%. The record does not identify which value is correct.","must":["5.8","10.2"],"forbid":[]},
{"id":"X05","class":"sparse","text":"55-year-old patient. Type 2 diabetes mellitus. No symptoms, investigations, results, or follow-up plan are documented in this packet.","must":["diabetes"],"forbid":[]},
{"id":"X06","class":"negative_evidence","text":"Patient explicitly denies chest pain, shortness of breath, fever and syncope. Routine blood pressure review only.","must":["blood pressure"],"forbid":[]},
{"id":"X07","class":"pending_followup","text":"Iron-deficiency anaemia suspected. Ferritin and full blood count ordered. Results are pending and follow-up is not documented.","must":["ferritin","blood"],"forbid":[]},
{"id":"X08","class":"normal_result","text":"Urinary frequency investigated. Urinalysis completed and documented as normal. No haematuria. No further tests ordered.","must":["urinalysis","normal"],"forbid":["haematuria"]},
{"id":"X09","class":"multi_problem","text":"Patient has hypertension and chronic kidney disease. Reports ankle swelling. Renal function test shows eGFR 28 mL/min/1.73m2. Nephrology review requested.","must":["ankle","28","nephrology"],"forbid":[]},
{"id":"X10","class":"minimal_missing","text":"Clinical note states only: 'abdominal pain'. No duration, severity, associated symptoms, examination, tests, results or plan supplied.","must":["abdominal pain"],"forbid":[]},
]

def objdict(x):
 if is_dataclass(x): return asdict(x)
 if hasattr(x,"model_dump"): return x.model_dump()
 if hasattr(x,"dict"): return x.dict()
 if hasattr(x,"__dict__"): return dict(x.__dict__)
 return {"value":str(x)}

def flatten(v):
 if isinstance(v,dict): return " ".join(flatten(x) for x in v.values())
 if isinstance(v,(list,tuple,set)): return " ".join(flatten(x) for x in v)
 return str(v)

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--model",default=DEFAULT_OLLAMA_MODEL)
 ap.add_argument("--timeout",type=int,default=3,help="Ollama health-check timeout only")
 args=ap.parse_args()
 try:
  requests.get("http://localhost:11434/api/tags",timeout=args.timeout).raise_for_status()
 except Exception as e:
  print("Gate 4 cannot run: Ollama unavailable:",e);raise SystemExit(3)

 rows=[];t0=time.perf_counter()
 for i,c in enumerate(CASES,1):
  started=time.perf_counter();err=None;out={}
  try:
   result=extract(c["text"],mode="Ollama MedGemma",model=args.model)
   out=objdict(result)
  except Exception as e: err=f"{type(e).__name__}: {e}"
  sec=round(time.perf_counter()-started,3); blob=flatten(out).lower()
  must_hits={x:(x.lower() in blob) for x in c["must"]}
  # "forbid" here means facts explicitly negated in source must not be hallucinated as positive evidence.
  # We record them for manual/structured inspection rather than naïvely failing on any mention.
  schema_ok=bool(out) and err is None
  rows.append({"id":c["id"],"class":c["class"],"seconds":sec,"schema_ok":schema_ok,"error":err,
               "required_evidence_hits":must_hits,"required_evidence_recall":round(sum(must_hits.values())/len(must_hits),4) if must_hits else 1.0,
               "negated_source_terms":c["forbid"],"output":out})
  print(f"{i:02d}/{len(CASES)} {c['id']} schema={'PASS' if schema_ok else 'FAIL'} {sec}s")

 schema_pass=sum(r["schema_ok"] for r in rows)
 evidence=sum(r["required_evidence_recall"] for r in rows)/len(rows)
 failures=sum(1 for r in rows if r["error"])
 # Gate 4A is intentionally strict on pipeline reliability, but evidence fidelity is reported,
 # not auto-"fixed". We want the first real model baseline.
 overall=(schema_pass==len(rows) and failures==0)
 report={"gate":"Gate 4A production-path MedGemma extraction","model":args.model,"total":len(rows),
         "schema_success":schema_pass,"schema_success_rate":round(schema_pass/len(rows),4),
         "mean_required_evidence_recall":round(evidence,4),"inference_failures":failures,
         "total_seconds":round(time.perf_counter()-t0,3),"pass":overall,"cases":rows,
         "note":"PASS here means production inference/schema reliability. Evidence fidelity and negation/conflict behaviour are baseline measurements for Gate 4B review, not silently repaired."}
 op=ROOT/"benchmark_results/gate4a_production_medgemma.json";op.parent.mkdir(exist_ok=True);op.write_text(json.dumps(report,indent=2,default=str))
 print("\n=== GATE 4A — PRODUCTION MEDGEMMA EXTRACTION ===")
 print(f"Schema success: {schema_pass}/{len(rows)}")
 print("Inference failures:",failures)
 print("Mean required-evidence recall:",f"{100*evidence:.1f}%")
 print("Total runtime:",report["total_seconds"],"s")
 print("Overall pipeline reliability:","PASS" if overall else "FAIL")
 print("Report:",op)
 raise SystemExit(0 if overall else 2)
if __name__=="__main__":main()

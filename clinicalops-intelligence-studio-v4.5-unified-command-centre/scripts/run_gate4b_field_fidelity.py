#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse,json,re,sys
ROOT=Path(__file__).resolve().parents[1]

def text(v):
 if isinstance(v,dict): return " ".join(text(x) for x in v.values())
 if isinstance(v,list): return " ".join(text(x) for x in v)
 return str(v or "")
def has(v,*terms):
 s=text(v).lower()
 return any(t.lower() in s for t in terms)
def result_blob(o): return text(o.get("received_results",[]))
def check(case):
 cid=case["id"]; o=case.get("output") or {}; checks=[]
 def add(name,ok,detail=""): checks.append({"check":name,"pass":bool(ok),"detail":detail})
 symptoms=o.get("symptoms",[]); ordered=o.get("ordered_tests",[]); missing=o.get("missing_results",[])
 red=o.get("red_flags",[]); mi=o.get("missing_information",[]); results=o.get("received_results",[])
 open_loop=o.get("open_loop"); priority=str(o.get("priority",""))

 if cid=="X01":
  add("captures fatigue",has(symptoms,"fatigue"))
  add("captures polyuria",has(symptoms,"polyuria","urination"))
  add("does not turn denied chest pain into symptom/red flag",not has(symptoms,"chest pain") and not has(red,"chest pain"))
  add("does not turn denied dyspnoea into symptom/red flag",not has(symptoms,"dysp","shortness of breath") and not has(red,"dysp","shortness of breath"))
 elif cid=="X02":
  add("captures chest pain",has(symptoms,"chest pain") or has(red,"chest pain"))
  add("recognises troponin ordered/pending",has(ordered,"troponin") or has(missing,"troponin"))
  add("pending troponin is unresolved",has(missing,"troponin") and open_loop is True)
  add("red-flag signal present",bool(red) or "urgent" in priority.lower() or "escalation" in priority.lower())
 elif cid=="X03":
  add("captures cough",has(symptoms,"cough"))
  add("captures fever",has(symptoms,"fever"))
  add("chest x-ray recognised",has(ordered,"x-ray","xray","radiograph") or has(missing,"x-ray","xray","radiograph"))
  add("missing x-ray result recognised",has(missing,"x-ray","xray","radiograph"))
  add("open loop true",open_loop is True)
 elif cid=="X04":
  rb=result_blob(o)
  add("preserves 5.8 result","5.8" in rb)
  add("preserves 10.2 result","10.2" in rb)
  add("does not silently collapse conflict",("5.8" in rb and "10.2" in rb))
  add("conflict/uncertainty represented",bool(mi) or has(o.get("model_notes",""),"conflict","uncertain","discrep","which value"))
 elif cid=="X05":
  add("captures diabetes context",has(o.get("clinical_context",""),"diabetes") or has(o.get("model_notes",""),"diabetes"))
  add("does not invent symptoms",len(symptoms)==0)
  add("does not invent ordered tests",len(ordered)==0)
  add("does not invent received results",len(results)==0)
  add("missing/limited information represented",bool(mi) or has(o.get("model_notes",""),"no symptoms","not documented","limited","missing"))
 elif cid=="X06":
  add("denied chest pain not positive",not has(symptoms,"chest pain") and not has(red,"chest pain"))
  add("denied breathlessness not positive",not has(symptoms,"shortness","dysp") and not has(red,"shortness","dysp"))
  add("denied fever not positive",not has(symptoms,"fever") and not has(red,"fever"))
  add("denied syncope not positive",not has(symptoms,"syncope") and not has(red,"syncope"))
  add("no artificial open loop",open_loop is False)
 elif cid=="X07":
  add("ferritin recognised",has(ordered,"ferritin") or has(missing,"ferritin"))
  add("FBC recognised",has(ordered,"full blood","fbc","blood count") or has(missing,"full blood","fbc","blood count"))
  add("pending results represented",bool(missing))
  add("open loop true",open_loop is True)
 elif cid=="X08":
  rb=result_blob(o)
  add("urinalysis result captured",has(rb,"urinalysis","urine"))
  add("normal status/finding preserved",has(rb,"normal"))
  add("negated haematuria not symptom/red flag",not has(symptoms,"haematuria","hematuria") and not has(red,"haematuria","hematuria"))
  add("no missing result invented",len(missing)==0)
  add("closed loop",open_loop is False)
 elif cid=="X09":
  rb=result_blob(o)
  add("ankle swelling captured",has(symptoms,"ankle swelling","swelling","oedema","edema"))
  add("eGFR 28 captured",("28" in rb and has(rb,"egfr","renal","glomerular")))
  add("abnormal renal result retained",has(rb,"abnormal","28"))
  add("nephrology follow-up represented",has(o,"nephrology"))
 elif cid=="X10":
  add("abdominal pain captured",has(symptoms,"abdominal pain") or has(o.get("clinical_context",""),"abdominal pain"))
  add("no tests invented",len(ordered)==0)
  add("no results invented",len(results)==0)
  add("missing information explicit",bool(mi))
 return checks

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--input",default=str(ROOT/"benchmark_results/gate4a_production_medgemma.json"))
 args=ap.parse_args(); p=Path(args.input)
 if not p.exists():
  print("Gate 4A result not found:",p)
  print("Run: python scripts/run_gate4a_production_medgemma.py")
  raise SystemExit(3)
 d=json.loads(p.read_text()); rows=[]
 for c in d["cases"]:
  checks=check(c); passed=sum(x["pass"] for x in checks)
  rows.append({"id":c["id"],"class":c["class"],"passed_checks":passed,"total_checks":len(checks),
               "pass":passed==len(checks),"checks":checks})
 total_checks=sum(r["total_checks"] for r in rows); passed_checks=sum(r["passed_checks"] for r in rows)
 cases_pass=sum(r["pass"] for r in rows)
 out={"gate":"Gate 4B field fidelity / hallucination / uncertainty","source_gate4a":str(p),
      "cases_passed":cases_pass,"total_cases":len(rows),"checks_passed":passed_checks,"total_checks":total_checks,
      "check_accuracy":round(passed_checks/total_checks,4),"pass":cases_pass==len(rows),"cases":rows,
      "acceptance":"All frozen field-level assertions pass. Failures are diagnostic and must be classified before changing prompt/schema/post-processing."}
 op=ROOT/"benchmark_results/gate4b_field_fidelity.json";op.write_text(json.dumps(out,indent=2))
 print("\n=== GATE 4B — FIELD FIDELITY / SAFETY ===")
 print(f"Cases passed: {cases_pass}/{len(rows)}")
 print(f"Checks passed: {passed_checks}/{total_checks} ({100*passed_checks/total_checks:.1f}%)")
 for r in rows:
  status="PASS" if r["pass"] else "FAIL"
  print(f"{status} {r['id']} {r['passed_checks']}/{r['total_checks']}")
  for x in r["checks"]:
   if not x["pass"]: print("   -",x["check"])
 print("Overall:","PASS" if out["pass"] else "FAIL")
 print("Report:",op)
 raise SystemExit(0 if out["pass"] else 2)
if __name__=="__main__":main()

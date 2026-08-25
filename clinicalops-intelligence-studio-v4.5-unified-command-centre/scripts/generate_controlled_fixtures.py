#!/usr/bin/env python3
from pathlib import Path
import argparse, csv, uuid
from datetime import date, timedelta

ANCHOR=date(2026,8,7)
CASES=[
 ("CTRL-AGE-49",49,7.5,30,1,1,0,"M","age",0),
 ("CTRL-AGE-50",50,7.5,30,1,1,0,"M","age",1),
 ("CTRL-AGE-70",70,7.5,30,1,1,0,"F","age",1),
 ("CTRL-AGE-71",71,7.5,30,1,1,0,"F","age",0),
 ("CTRL-HBA1C-7.49",60,7.49,30,1,1,0,"M","hba1c",0),
 ("CTRL-HBA1C-7.50",60,7.50,30,1,1,0,"M","hba1c",1),
 ("CTRL-HBA1C-7.51",60,7.51,30,1,1,0,"M","hba1c",1),
 ("CTRL-TIME-89",60,7.5,89,1,1,0,"F","recency",1),
 ("CTRL-TIME-90",60,7.5,90,1,1,0,"F","recency",1),
 ("CTRL-TIME-91",60,7.5,91,1,1,0,"F","recency",0),
 ("CTRL-NO-CKD",60,7.5,30,1,1,0,"M","base",1),
 ("CTRL-CKD",60,7.5,30,1,1,1,"M","base",0),
 ("CTRL-DIAB-HTN",60,7.5,30,1,1,0,"F","base",1),
 ("CTRL-DIAB-ONLY",60,7.5,30,1,0,0,"F","base",0),
 ("CTRL-DUPLICATE",60,7.5,30,1,1,0,"M","quality",1),
 ("CTRL-SPARSE",60,7.5,30,1,1,0,"M","quality",1),
 ("CTRL-DENSE",60,7.5,30,1,1,0,"F","quality",1),
 ("CTRL-MISSING-SEX",60,7.5,30,1,1,0,"","quality",1),
 ("CTRL-CONFLICT",60,7.5,30,1,1,0,"F","quality",1),
]
def w(path,fields):
 f=open(path,"w",newline="",encoding="utf-8")
 writer=csv.DictWriter(f,fieldnames=fields)
 writer.writeheader()
 return f,writer
def birth_for_age(age):
 # Guarantees exact integer age at anchor using ordinary birthday semantics.
 return date(ANCHOR.year-age,1,15)
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--out",required=True); a=ap.parse_args()
 out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
 pf,pw=w(out/"patients.csv",["Id","BIRTHDATE","DEATHDATE","SSN","DRIVERS","PASSPORT","PREFIX","FIRST","LAST","SUFFIX","MAIDEN","MARITAL","RACE","ETHNICITY","GENDER","BIRTHPLACE","ADDRESS","CITY","STATE","COUNTY","FIPS","ZIP","LAT","LON","HEALTHCARE_EXPENSES","HEALTHCARE_COVERAGE","INCOME"])
 cf,cw=w(out/"conditions.csv",["START","STOP","PATIENT","ENCOUNTER","SYSTEM","CODE","DESCRIPTION"])
 ef,ew=w(out/"encounters.csv",["Id","START","STOP","PATIENT","ORGANIZATION","PROVIDER","PAYER","ENCOUNTERCLASS","CODE","DESCRIPTION","BASE_ENCOUNTER_COST","TOTAL_CLAIM_COST","PAYER_COVERAGE","REASONCODE","REASONDESCRIPTION"])
 of,ow=w(out/"observations.csv",["DATE","PATIENT","ENCOUNTER","CATEGORY","CODE","DESCRIPTION","VALUE","UNITS","TYPE"])
 gf,gw=w(out/"controlled_ground_truth.csv",["patient_id","case_id","dimension","expected_base","expected_hba1c","expected_recency90"])
 for idx,(case,age,hba,days,diab,htn,ckd,sex,dim,expected) in enumerate(CASES):
  pid=str(uuid.uuid5(uuid.NAMESPACE_DNS,"clinicalops-"+case)); eid=str(uuid.uuid5(uuid.NAMESPACE_DNS,"enc-"+case))
  pw.writerow({"Id":pid,"BIRTHDATE":birth_for_age(age).isoformat(),"DEATHDATE":"","SSN":"","DRIVERS":"","PASSPORT":"","PREFIX":"","FIRST":"Test","LAST":case,"SUFFIX":"","MAIDEN":"","MARITAL":"S","RACE":"synthetic","ETHNICITY":"synthetic","GENDER":sex,"BIRTHPLACE":"United Kingdom","ADDRESS":"Synthetic","CITY":"London","STATE":"England","COUNTY":"Synthetic","FIPS":"","ZIP":"ZZ1 1ZZ","LAT":"51.5","LON":"-0.1","HEALTHCARE_EXPENSES":"0","HEALTHCARE_COVERAGE":"0","INCOME":"0"})
  dt=ANCHOR-timedelta(days=days)
  ew.writerow({"Id":eid,"START":dt.isoformat(),"STOP":dt.isoformat(),"PATIENT":pid,"ORGANIZATION":"UK-SYNTH","PROVIDER":"UK-SYNTH","PAYER":"NHS-SYNTHETIC","ENCOUNTERCLASS":"ambulatory","CODE":"","DESCRIPTION":"Synthetic benchmark encounter","BASE_ENCOUNTER_COST":"0","TOTAL_CLAIM_COST":"0","PAYER_COVERAGE":"0","REASONCODE":"","REASONDESCRIPTION":""})
  dx=[]
  if diab: dx.append("Type 2 diabetes mellitus")
  if htn: dx.append("Essential hypertension")
  if ckd: dx.append("Chronic kidney disease")
  for d in dx:
   cw.writerow({"START":dt.isoformat(),"STOP":"","PATIENT":pid,"ENCOUNTER":eid,"SYSTEM":"SNOMED-CT","CODE":"","DESCRIPTION":d})
   if case=="CTRL-DUPLICATE" and d=="Essential hypertension":
    cw.writerow({"START":dt.isoformat(),"STOP":"","PATIENT":pid,"ENCOUNTER":eid,"SYSTEM":"SNOMED-CT","CODE":"","DESCRIPTION":d})
  obs_count=1 if case=="CTRL-SPARSE" else (250 if case=="CTRL-DENSE" else 2)
  for j in range(obs_count):
   desc="Hemoglobin A1c/Hemoglobin.total in Blood" if j==0 else "Systolic Blood Pressure"
   val=hba if j==0 else 120+(j%20); unit="%" if j==0 else "mm[Hg]"
   ow.writerow({"DATE":dt.isoformat(),"PATIENT":pid,"ENCOUNTER":eid,"CATEGORY":"laboratory" if j==0 else "vital-signs","CODE":"","DESCRIPTION":desc,"VALUE":val,"UNITS":unit,"TYPE":"numeric"})
  if case=="CTRL-CONFLICT":
   ow.writerow({"DATE":(dt-timedelta(days=30)).isoformat(),"PATIENT":pid,"ENCOUNTER":eid,"CATEGORY":"laboratory","CODE":"","DESCRIPTION":"Hemoglobin A1c/Hemoglobin.total in Blood","VALUE":10.2,"UNITS":"%","TYPE":"numeric"})
  base=(50<=age<=70 and bool(diab) and bool(htn) and not bool(ckd))
  hba_ok=base and hba>=7.5
  rec=base and days<=90
  gw.writerow({"patient_id":pid,"case_id":case,"dimension":dim,"expected_base":int(base),"expected_hba1c":int(hba_ok),"expected_recency90":int(rec)})
 for f in [pf,cf,ef,of,gf]: f.close()
 print(f"Generated {len(CASES)} controlled fixtures in {out}")
if __name__=="__main__": main()

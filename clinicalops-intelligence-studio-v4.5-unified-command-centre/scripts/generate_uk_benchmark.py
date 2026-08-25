#!/usr/bin/env python3
"""Generate a UK-only synthetic benchmark population compatible with ClinicalOps.

This is NOT NHS data. All identities, sites and postcodes are synthetic.
It intentionally injects labelled edge cases for correctness/stress testing.
"""
from __future__ import annotations
import argparse, csv, json, random, uuid
from datetime import date, datetime, timedelta
from pathlib import Path
import numpy as np

ANCHOR=date(2026,8,7)
UK=[
("England","London","London","SW1A 1ZZ",.20),("England","West Midlands","Birmingham","B1 1AA",.09),
("England","North West","Manchester","M1 1AE",.09),("England","Yorkshire and the Humber","Leeds","LS1 1UR",.07),
("England","North West","Liverpool","L1 8JQ",.05),("England","South West","Bristol","BS1 5AH",.06),
("England","North East","Newcastle upon Tyne","NE1 7RU",.05),("England","East of England","Cambridge","CB2 1TN",.05),
("England","South East","Oxford","OX1 2JD",.06),("Scotland","Scotland","Glasgow","G1 1AA",.07),
("Scotland","Scotland","Edinburgh","EH1 1YZ",.05),("Wales","Wales","Cardiff","CF10 1EP",.04),
("Northern Ireland","Northern Ireland","Belfast","BT1 5GS",.03),("England","East Midlands","Nottingham","NG1 5FS",.04)
]
DX=[("Essential hypertension",.24),("Type 2 diabetes mellitus",.12),("Obesity",.15),("Hyperlipidemia",.14),("Asthma",.11),("Chronic kidney disease",.055),("Coronary artery disease",.045),("Heart failure",.025),("Depression",.10),("Osteoarthritis",.10),("Atrial fibrillation",.025),("COPD",.035)]
FIRST=["Amelia","Olivia","Isla","Emily","Ava","Noah","Oliver","George","Arthur","Muhammad","Sophie","Grace","Freddie","Jack","Harry","Priya","Aisha","Arjun","Ravi","Meera"]
LAST=["Smith","Jones","Taylor","Brown","Williams","Wilson","Johnson","Davies","Patel","Khan","Singh","Shah","Evans","Thomas","Roberts","Walker"]

def writer(path, fields):
    f=open(path,"w",newline="",encoding="utf-8"); w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); return f,w

def weighted_geo(r):
    vals=[x[:4] for x in UK]; weights=[x[4] for x in UK]; return r.choices(vals,weights=weights,k=1)[0]

def dob_for_age(age,r):
    # Keep benchmark age deterministic relative to anchor.
    day=r.randint(1,28); month=r.randint(1,12); year=ANCHOR.year-age
    d=date(year,month,day)
    if (month,day)>(ANCHOR.month,ANCHOR.day): d=date(year-1,month,day)
    return d

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--patients",type=int,default=300000); ap.add_argument("--out",default="benchmark_data/uk_300k"); ap.add_argument("--seed",type=int,default=260807); ap.add_argument("--edge-rate",type=float,default=.05); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True); r=random.Random(args.seed); np.random.seed(args.seed)
    pf,pw=writer(out/"patients.csv",["Id","BIRTHDATE","DEATHDATE","SSN","DRIVERS","PASSPORT","PREFIX","FIRST","LAST","SUFFIX","MAIDEN","MARITAL","RACE","ETHNICITY","GENDER","BIRTHPLACE","ADDRESS","CITY","STATE","COUNTY","FIPS","ZIP","LAT","LON","HEALTHCARE_EXPENSES","HEALTHCARE_COVERAGE","INCOME"])
    cf,cw=writer(out/"conditions.csv",["START","STOP","PATIENT","ENCOUNTER","SYSTEM","CODE","DESCRIPTION"])
    ef,ew=writer(out/"encounters.csv",["Id","START","STOP","PATIENT","ORGANIZATION","PROVIDER","PAYER","ENCOUNTERCLASS","CODE","DESCRIPTION","BASE_ENCOUNTER_COST","TOTAL_CLAIM_COST","PAYER_COVERAGE","REASONCODE","REASONDESCRIPTION"])
    of,ow=writer(out/"observations.csv",["DATE","PATIENT","ENCOUNTER","CATEGORY","CODE","DESCRIPTION","VALUE","UNITS","TYPE"])
    mf,mw=writer(out/"medications.csv",["START","STOP","PATIENT","PAYER","ENCOUNTER","CODE","DESCRIPTION","BASE_COST","PAYER_COVERAGE","DISPENSES","TOTALCOST","REASONCODE","REASONDESCRIPTION"])
    gf,gw=writer(out/"benchmark_ground_truth.csv",["patient_id","scenario","expected_base_cohort","expected_hba1c_cohort","expected_reason","injected"])
    # Empty compatibility tables used by analysis pages.
    extras={"procedures.csv":["START","STOP","PATIENT","ENCOUNTER","SYSTEM","CODE","DESCRIPTION","BASE_COST","REASONCODE","REASONDESCRIPTION"],"imaging_studies.csv":["Id","DATE","PATIENT","ENCOUNTER","SERIES_UID","BODYSITE_CODE","BODYSITE_DESCRIPTION","MODALITY_CODE","MODALITY_DESCRIPTION","INSTANCE_UID","SOP_CODE","SOP_DESCRIPTION","PROCEDURE_CODE"],"claims.csv":["Id","PATIENT","PROVIDER","PRIMARYPATIENTINSURANCEID","SECONDARYPATIENTINSURANCEID","DEPARTMENTID","PATIENTDEPARTMENTID","DIAGNOSIS1","DIAGNOSIS2","DIAGNOSIS3","DIAGNOSIS4","DIAGNOSIS5","DIAGNOSIS6","DIAGNOSIS7","DIAGNOSIS8","REFERRINGPROVIDERID","APPOINTMENTID","CURRENTILLNESSDATE","SERVICEDATE","SUPERVISINGPROVIDERID","STATUS1","STATUS2","STATUSP","OUTSTANDING1","OUTSTANDING2","OUTSTANDINGP","LASTBILLEDDATE1","LASTBILLEDDATE2","LASTBILLEDDATEP","HEALTHCARECLAIMTYPEID1","HEALTHCARECLAIMTYPEID2"]}
    extra_handles=[]
    for fn,fields in extras.items(): extra_handles.append(writer(out/fn,fields)[0])
    scenario_counts={}
    for i in range(args.patients):
        pid=str(uuid.UUID(int=r.getrandbits(128))); nation,region,city,postcode=weighted_geo(r)
        injected=i < max(100, int(args.patients*args.edge_rate))
        scenario="BASELINE"; age=int(np.clip(np.random.normal(49,22),0,100)); sex=r.choice(["M","F"])
        has_diab=r.random()<.12; has_htn=r.random()<.24; has_ckd=r.random()<.055; hba1c=round(r.uniform(5.0,10.5),2) if has_diab else round(r.uniform(4.5,6.2),2)
        encounter_days=r.randint(0,365*4)
        if injected:
            modes=["UK-AGE-LOW","UK-AGE-HIGH","UK-AGE-BELOW","UK-AGE-ABOVE","UK-DX-MISSING-HTN","UK-DX-CKD","UK-OBS-THRESHOLD","UK-OBS-BELOW","UK-OBS-ABOVE","UK-TIME-90","UK-TIME-91","UK-DATA-SPARSE","UK-DATA-DENSE","UK-DATA-DUP","UK-DATA-CONFLICT","UK-DATA-MISSING-SEX"]
            scenario=modes[i%len(modes)]; has_diab=True; has_htn=True; has_ckd=False; age=r.randint(50,70); encounter_days=r.randint(0,60); hba1c=8.0
            if scenario=="UK-AGE-LOW": age=50
            elif scenario=="UK-AGE-HIGH": age=70
            elif scenario=="UK-AGE-BELOW": age=49
            elif scenario=="UK-AGE-ABOVE": age=71
            elif scenario=="UK-DX-MISSING-HTN": has_htn=False
            elif scenario=="UK-DX-CKD": has_ckd=True
            elif scenario=="UK-OBS-THRESHOLD": hba1c=7.50
            elif scenario=="UK-OBS-BELOW": hba1c=7.49
            elif scenario=="UK-OBS-ABOVE": hba1c=7.51
            elif scenario=="UK-TIME-90": encounter_days=90
            elif scenario=="UK-TIME-91": encounter_days=91
            elif scenario=="UK-DATA-MISSING-SEX": sex=""
        dob=dob_for_age(age,r); pw.writerow({"Id":pid,"BIRTHDATE":dob,"DEATHDATE":"","SSN":"","DRIVERS":"","PASSPORT":"","PREFIX":"","FIRST":r.choice(FIRST),"LAST":r.choice(LAST),"SUFFIX":"","MAIDEN":"","MARITAL":"M" if age>30 and r.random()<.55 else "S","RACE":r.choice(["white","asian","black","other"]),"ETHNICITY":r.choice(["nonhispanic","hispanic"]),"GENDER":sex,"BIRTHPLACE":nation,"ADDRESS":f"{r.randint(1,220)} Synthetic Road","CITY":city,"STATE":region,"COUNTY":nation,"FIPS":"","ZIP":postcode,"LAT":"","LON":"","HEALTHCARE_EXPENSES":0,"HEALTHCARE_COVERAGE":0,"INCOME":r.randint(18000,90000)})
        enc_n=1 if scenario=="UK-DATA-SPARSE" else (30 if scenario=="UK-DATA-DENSE" else r.randint(2,8)); enc_ids=[]
        for j in range(enc_n):
            eid=str(uuid.UUID(int=r.getrandbits(128))); enc_ids.append(eid); days=encounter_days if j==0 else r.randint(0,365*5); dt=datetime.combine(ANCHOR-timedelta(days=days),datetime.min.time())+timedelta(hours=r.randint(8,17))
            ew.writerow({"Id":eid,"START":dt.isoformat(),"STOP":(dt+timedelta(minutes=30)).isoformat(),"PATIENT":pid,"ORGANIZATION":f"UKSITE-{(hash(city)%60)+1:03d}","PROVIDER":"SYNTHETIC","PAYER":"NHS-SYNTHETIC","ENCOUNTERCLASS":r.choice(["ambulatory","outpatient","emergency","inpatient"]),"CODE":"","DESCRIPTION":"Synthetic NHS-style encounter","BASE_ENCOUNTER_COST":0,"TOTAL_CLAIM_COST":0,"PAYER_COVERAGE":0,"REASONCODE":"","REASONDESCRIPTION":""})
        start=(ANCHOR-timedelta(days=r.randint(100,2500))).isoformat(); eid=enc_ids[0]
        present=[]
        if has_diab: present.append("Type 2 diabetes mellitus")
        if has_htn: present.append("Essential hypertension")
        if has_ckd: present.append("Chronic kidney disease")
        for desc,p in DX:
            if desc in present: continue
            if r.random()<p: present.append(desc)
        for desc in present:
            cw.writerow({"START":start,"STOP":"","PATIENT":pid,"ENCOUNTER":eid,"SYSTEM":"SNOMED-CT","CODE":"","DESCRIPTION":desc})
            if scenario=="UK-DATA-DUP" and desc=="Essential hypertension": cw.writerow({"START":start,"STOP":"","PATIENT":pid,"ENCOUNTER":eid,"SYSTEM":"SNOMED-CT","CODE":"","DESCRIPTION":desc})
        obs_n=2 if scenario=="UK-DATA-SPARSE" else (80 if scenario=="UK-DATA-DENSE" else r.randint(4,12))
        for j in range(obs_n):
            dt=ANCHOR-timedelta(days=r.randint(0,730)); desc="Systolic Blood Pressure"; val=r.randint(100,180); units="mm[Hg]"
            if j==0 and has_diab: desc="Hemoglobin A1c/Hemoglobin.total in Blood"; val=hba1c; units="%"
            if scenario=="UK-DATA-CONFLICT" and j in (0,1): desc="Hemoglobin A1c/Hemoglobin.total in Blood"; val=5.8 if j==0 else 10.2; units="%"
            ow.writerow({"DATE":dt.isoformat(),"PATIENT":pid,"ENCOUNTER":eid,"CATEGORY":"laboratory" if "A1c" in desc else "vital-signs","CODE":"","DESCRIPTION":desc,"VALUE":val,"UNITS":units,"TYPE":"numeric"})
        if has_diab: mw.writerow({"START":start,"STOP":"","PATIENT":pid,"PAYER":"NHS-SYNTHETIC","ENCOUNTER":eid,"CODE":"","DESCRIPTION":"Metformin 500 MG Oral Tablet","BASE_COST":0,"PAYER_COVERAGE":0,"DISPENSES":1,"TOTALCOST":0,"REASONCODE":"","REASONDESCRIPTION":"Type 2 diabetes mellitus"})
        final_conditions = set(present)
        actual_diabetes = "Type 2 diabetes mellitus" in final_conditions
        actual_hypertension = "Essential hypertension" in final_conditions
        actual_ckd = "Chronic kidney disease" in final_conditions
        base = (50 <= age <= 70 and actual_diabetes and actual_hypertension and not actual_ckd)
        hba = base and hba1c >= 7.5
        reason = ("eligible" if base else "age" if not 50 <= age <= 70 else "ckd" if actual_ckd
                  else "missing_diabetes" if not actual_diabetes else "missing_hypertension")
        gw.writerow({"patient_id":pid,"scenario":scenario,"expected_base_cohort":int(base),"expected_hba1c_cohort":int(hba),"expected_reason":reason,"injected":int(injected)})
        scenario_counts[scenario]=scenario_counts.get(scenario,0)+1
        if (i+1)%25000==0: print(f"generated {i+1:,}/{args.patients:,}")
    for f in [pf,cf,ef,of,mf,gf,*extra_handles]: f.close()
    # UK synthetic site operations ground truth.
    sf,sw=writer(out/"benchmark_sites.csv",["site_id","site_name","nation","city","risk_profile","expected_risk_rank_group","open_queries","oldest_query_days","overdue_visits","major_deviations","enrolled"])
    profiles=["excellent","slow_enrolment","query_problem","visit_problem","protocol_problem","catastrophic"]
    cities=[x[:4] for x in UK]
    for i in range(60):
        nation,region,city,pc=cities[i%len(cities)]; prof=profiles[i%len(profiles)]
        vals={"excellent":(3,4,1,0,45),"slow_enrolment":(5,8,2,1,8),"query_problem":(48,72,3,1,30),"visit_problem":(8,15,24,2,32),"protocol_problem":(12,20,6,14,28),"catastrophic":(65,95,31,18,20)}[prof]
        sw.writerow({"site_id":f"UK-{i+1:03d}","site_name":f"Synthetic {city} Research Site {i+1}","nation":nation,"city":city,"risk_profile":prof,"expected_risk_rank_group":5 if prof=="catastrophic" else 4 if prof in ("query_problem","visit_problem","protocol_problem") else 2 if prof=="slow_enrolment" else 1,"open_queries":vals[0],"oldest_query_days":vals[1],"overdue_visits":vals[2],"major_deviations":vals[3],"enrolled":vals[4]})
    sf.close()
    manifest={"generated_at":datetime.now().isoformat(),"anchor_date":ANCHOR.isoformat(),"patients":args.patients,"country":"United Kingdom","synthetic_only":True,"seed":args.seed,"edge_rate":args.edge_rate,"scenario_counts":scenario_counts,"notes":"All names, postcodes and sites are synthetic benchmark data. Not NHS patient data."}
    (out/"benchmark_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(manifest,indent=2)); print(f"\nOutput: {out.resolve()}")
if __name__=="__main__": main()

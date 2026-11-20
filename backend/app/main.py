from __future__ import annotations
import json, os, uuid
from pathlib import Path
from datetime import datetime
import httpx
from fastapi import FastAPI, Depends, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO, StringIO
import pandas as pd
from .config import settings
from .db import Base, engine, get_db
from .models import AuditRecord, UploadDraft, BillingRecord
from .schemas import ManualAuditIn, ConfirmDraftIn, ExplainIn, EvaluationIn
from .ocr import SUPPORTED, read_bill, extract_fields
from .engine import audit_bill, evaluate_binary, isolation_forest, cluster_consumers, detect_mean_shift, analyse_bill_periods, analyse_daily_meter, synthetic_benchmark, METHODOLOGY
from .tariffs import check_eligibility

if settings.app_env == "development":
    Base.metadata.create_all(bind=engine)
    from .db import migrate_schema
    migrate_schema()
app=FastAPI(title="ClearWatt 2.2 API",version="2.2.0",description="Consumer-first electricity bill auditing and utility intelligence")
app.add_middleware(CORSMiddleware,allow_origins=settings.origins,allow_credentials=True,allow_methods=["GET","POST"],allow_headers=["Content-Type","Authorization"])
UPLOAD=Path(settings.upload_dir);UPLOAD.mkdir(parents=True,exist_ok=True)
def record_out(row:AuditRecord):return {"id":str(row.id),"bill_id":str(row.bill_id) if row.bill_id else None,"consumer_ref":row.consumer_ref,"meter_ref":row.meter_ref,"discom":row.discom,"period_start":row.period_start,"period_end":row.period_end,"units":row.units,"amount":row.amount,"created_at":row.created_at.isoformat(),"status":row.status,**json.loads(row.result_json)}
def run_audit(payload:dict,source_filename:str|None,db:Session):
    start=datetime.fromisoformat(payload["period_start"]) if isinstance(payload["period_start"],str) else payload["period_start"];end=datetime.fromisoformat(payload["period_end"]) if isinstance(payload["period_end"],str) else payload["period_end"];days=(end-start).days+1
    if days<=0:raise HTTPException(422,"Billing period must contain at least one day.")
    if payload.get("meter_reading_previous") is not None and payload.get("meter_reading_current") is not None:
        if payload["meter_reading_current"]<payload["meter_reading_previous"]:raise HTTPException(422,"Current meter reading is below previous reading. Please verify the readings or record meter replacement.")
    # Only bills from the same meter reference contribute historical context.
    history=payload.get("history")
    meter_ref=(payload.get("meter_ref") or "").strip()
    if not history:
        history=[]
        current_start=start.date() if hasattr(start,"date") else start
        if meter_ref:
            rows=db.query(BillingRecord).filter(BillingRecord.meter_ref==meter_ref).order_by(BillingRecord.period_end.asc()).all()
            for previous in rows:
                try:
                    prev_start=datetime.fromisoformat(previous.period_start).date(); prev_end=datetime.fromisoformat(previous.period_end).date()
                    if prev_end < current_start:
                        history.append({"period_start":prev_start.isoformat(),"period_end":prev_end.isoformat(),"period_days":(prev_end-prev_start).days+1,"units":float(previous.units),"amount":float(previous.amount)})
                except (ValueError,TypeError):
                    continue
        history.sort(key=lambda item:item["period_end"])
        history=history[-12:]
    result=audit_bill(units=payload["units"],amount=payload["amount"],period_days=days,history=history,meter_previous=payload.get("meter_reading_previous"),meter_current=payload.get("meter_reading_current"))
    current_period={"period_end":end.date().isoformat() if hasattr(end,"date") else str(end),"period_days":days,"units":float(payload["units"]),"amount":float(payload["amount"])}
    result["algorithm_analysis"]=analyse_bill_periods(history,current_period)
    tariff=check_eligibility(payload["period_end"],payload.get("consumer_category","domestic"),payload.get("supply_area"))
    result["tariff_check"]={"status":tariff.status,"message":tariff.message,"source":tariff.source}
    result["findings"]=[{"code":s["code"],"title":s["title"],"severity":s["severity"],"explanation":s["explanation"],"observed":s.get("observed"),"baseline":s.get("baseline"),"change_pct":s.get("change_pct"),"method":s["method"]} for s in result.pop("signals")]
    result["notices"]=[result.pop("notice"),"UPPCL tariff verification is currently unavailable; no tariff correctness conclusion has been made."]
    chart_history=[]
    for h in history[-5:]:
        h_days=int(h.get("period_days",0) or 0)
        if h_days>0:
            chart_history.append({"period":h.get("period_end",""),"units":float(h["units"]),"daily_units":round(float(h["units"])/h_days,3),"amount":float(h.get("amount",0) or 0)})
    chart_history.append({"period":current_period["period_end"],"units":float(payload["units"]),"daily_units":round(float(payload["units"])/days,3),"amount":float(payload["amount"])})
    result["history"]=chart_history
    result["recommendations"]=result.get("recommendations",[])
    bill=None
    start_key=str(start.date() if hasattr(start,"date") else start); end_key=str(end.date() if hasattr(end,"date") else end)
    if meter_ref:
        bill=db.query(BillingRecord).filter(BillingRecord.meter_ref==meter_ref,BillingRecord.period_start==start_key,BillingRecord.period_end==end_key).first()
    if bill is None:
        bill=BillingRecord(consumer_ref=payload.get("consumer_ref"),meter_ref=meter_ref or None,discom=payload.get("discom"),period_start=start_key,period_end=end_key,units=float(payload["units"]),amount=float(payload["amount"]),source_filename=source_filename,payload_json=json.dumps(payload))
        db.add(bill);db.flush()
    else:
        bill.consumer_ref=payload.get("consumer_ref") or bill.consumer_ref; bill.discom=payload.get("discom") or bill.discom; bill.units=float(payload["units"]); bill.amount=float(payload["amount"]); bill.source_filename=source_filename or bill.source_filename; bill.payload_json=json.dumps(payload)
    row=AuditRecord(bill_id=bill.id,status=result["status"],consumer_ref=payload.get("consumer_ref"),meter_ref=meter_ref or None,discom=payload.get("discom"),period_start=start_key,period_end=end_key,units=float(payload["units"]),amount=float(payload["amount"]),source_filename=source_filename,payload_json=json.dumps(payload),result_json=json.dumps(result))
    db.add(row);db.commit();db.refresh(row);return record_out(row)

@app.get("/api/health")
def health():return {"status":"ok","service":"clearwatt-2.2","environment":settings.app_env,"database":"postgresql" if settings.database_url.startswith("postgres") else "sqlite-development","ai_configured":bool(settings.openrouter_api_key)}
@app.get("/api/methodology")
def methodology():return METHODOLOGY
@app.get("/api/ml/benchmark")
def ml_benchmark():return synthetic_benchmark()
@app.post("/api/audits/upload")
async def upload_bill(file:UploadFile=File(...),db:Session=Depends(get_db)):
    suffix=Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:raise HTTPException(415,"Upload a PDF, PNG, JPG or WEBP electricity bill.")
    content=await file.read(settings.max_upload_mb*1024*1024+1)
    if len(content)>settings.max_upload_mb*1024*1024:raise HTTPException(413,f"File is larger than {settings.max_upload_mb} MB.")
    stored=UPLOAD/f"{uuid.uuid4().hex}{suffix}";stored.write_bytes(content)
    try:text,engine_name=read_bill(stored);fields=extract_fields(text)
    except Exception as exc:
        stored.unlink(missing_ok=True);raise HTTPException(422,f"We could not read this bill. Try a clearer image or enter the details manually. ({type(exc).__name__})")
    draft=UploadDraft(source_filename=(file.filename or "bill")[:255],file_path=str(stored),extracted_json=json.dumps(fields),status="needs_review")
    db.add(draft);db.commit();db.refresh(draft)
    return {"draft_id":draft.id,"status":"needs_review","summary":"We’ve read the bill. Please check the details before we analyse it.","extracted":fields,"ocr_engine":engine_name,"text_detected":bool(text.strip()),"notice":"OCR can misread numbers. Confirm every field against the original bill before continuing."}
@app.post("/api/audits/confirm")
def confirm_bill(req:ConfirmDraftIn,db:Session=Depends(get_db)):
    draft=db.get(UploadDraft,req.draft_id)
    if not draft or draft.status!="needs_review":raise HTTPException(404,"This bill review session is unavailable or already completed.")
    payload=req.model_dump(mode="json",exclude={"draft_id"});result=run_audit(payload,draft.source_filename,db);draft.status="completed";db.commit();return result
@app.post("/api/audits/manual")
def manual_bill(req:ManualAuditIn,db:Session=Depends(get_db)):
    return run_audit(req.model_dump(mode="json"),None,db)
@app.get("/api/audits")
def list_audits(search:str|None=None,status:str|None=None,discom:str|None=None,meter_ref:str|None=None,db:Session=Depends(get_db)):
    query=db.query(AuditRecord).order_by(AuditRecord.id.desc())
    if status: query=query.filter(AuditRecord.status==status)
    if discom: query=query.filter(AuditRecord.discom.ilike(f"%{discom}%"))
    if meter_ref: query=query.filter(AuditRecord.meter_ref.ilike(f"%{meter_ref}%"))
    items=[]
    for x in query.limit(500).all():
        payload=json.loads(x.payload_json); result=json.loads(x.result_json); summary=result.get("summary",""); findings=result.get("findings",[])
        if search:
            needle=search.lower(); hay=" ".join([str(x.id),str(x.consumer_ref or ""),str(x.meter_ref or ""),str(x.discom or ""),str(x.period_start or ""),str(x.period_end or ""),summary]+[f.get("title","") for f in findings]).lower()
            if needle not in hay: continue
        items.append({"id":str(x.id),"bill_id":str(x.bill_id) if x.bill_id else None,"created_at":x.created_at.isoformat(),"consumer_ref":x.consumer_ref,"meter_ref":x.meter_ref,"discom":x.discom,"period_start":x.period_start or payload.get("period_start"),"period_end":x.period_end or payload.get("period_end"),"units":x.units if x.units is not None else payload.get("units"),"amount":x.amount if x.amount is not None else payload.get("amount"),"status":x.status,"summary":summary,"finding_count":len(findings),"finding_titles":[f.get("title") for f in findings]})
    return items

@app.get("/api/audits/summary")
def audit_summary(db:Session=Depends(get_db)):
    audits=db.query(AuditRecord).all(); bills=db.query(BillingRecord).all()
    flagged=sum(1 for row in audits if json.loads(row.result_json).get("findings"))
    return {"audit_runs":len(audits),"unique_bills":len(bills),"distinct_meters":len({b.meter_ref for b in bills if b.meter_ref}),"flagged_audits":flagged,"stored_records":len(bills),"notice":"Local development summary only. No authenticated DISCOM access is enabled."}

@app.get("/api/audits/{audit_id}")
def get_audit(audit_id:int,db:Session=Depends(get_db)):
    row=db.get(AuditRecord,audit_id)
    if not row:raise HTTPException(404,"Bill check not found.")
    return record_out(row)
@app.get("/api/audits/{audit_id}/report")
def report(audit_id:int,db:Session=Depends(get_db)):
    row=db.get(AuditRecord,audit_id)
    if not row:raise HTTPException(404,"Bill check not found.")
    data=json.loads(row.result_json);payload=json.loads(row.payload_json)
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    buf=BytesIO();doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=17*mm,leftMargin=17*mm,topMargin=16*mm,bottomMargin=16*mm,title=f"ClearWatt Bill Intelligence Report {audit_id}")
    styles=getSampleStyleSheet();styles.add(ParagraphStyle(name="CWTitle",parent=styles["Title"],fontName="Helvetica-Bold",fontSize=18,leading=22,textColor=colors.HexColor("#20372e"),spaceAfter=8));styles.add(ParagraphStyle(name="CWSection",parent=styles["Heading2"],fontName="Helvetica-Bold",fontSize=12,leading=15,textColor=colors.HexColor("#317d63"),spaceBefore=10,spaceAfter=5));styles.add(ParagraphStyle(name="CWBody",parent=styles["BodyText"],fontSize=9.5,leading=14,spaceAfter=6));styles.add(ParagraphStyle(name="CWNote",parent=styles["BodyText"],fontSize=8,leading=11,textColor=colors.HexColor("#68766f"),spaceAfter=4))
    story=[Paragraph("ClearWatt | Electricity Bill Intelligence Report",styles["CWTitle"]),Paragraph(f"Audit #{audit_id} · Generated {row.created_at.date()} · Billing period {payload.get('period_start')} to {payload.get('period_end')}",styles["CWNote"]),Paragraph("Overall assessment",styles["CWSection"]),Paragraph(data.get("summary","Analysis completed."),styles["CWBody"]),Paragraph("An unusual consumption pattern is a reason to review the bill, not proof of incorrect billing. Tariff correctness is not confirmed unless the applicable tariff has been verified.",styles["CWBody"])]
    units=float(payload.get("units",0)); amount=float(payload.get("amount",0)); start_date=datetime.fromisoformat(payload["period_start"]); end_date=datetime.fromisoformat(payload["period_end"]); days=(end_date-start_date).days+1; daily=units/days if days else 0; baseline=data.get("baseline") or {}; med=baseline.get("daily_units_median")
    story.append(Paragraph("Bill details and calculated indicators",styles["CWSection"])); rows=[["Field","Value"],["Energy consumed",f"{units:.2f} kWh"],["Billing period",f"{days} days"],["Average daily consumption",f"{daily:.2f} kWh/day"],["Total bill amount",f"INR {amount:,.2f}"],["Average amount per day",f"INR {amount/days:,.2f}" if days else "Not available"],["Historical median daily use",f"{med:.2f} kWh/day" if med is not None else "Insufficient history"],["Difference from baseline",f"{daily-med:+.2f} kWh/day" if med is not None else "Not calculated"],["Change from baseline",f"{baseline.get('usage_change_pct'):+.1f}%" if baseline.get("usage_change_pct") is not None else "Not calculated"],["Modified Z-score",f"{baseline.get('modified_z'):.2f}" if baseline.get("modified_z") is not None else "Not calculated"]]
    tbl=Table(rows,colWidths=[68*mm,91*mm],repeatRows=1);tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e8f3ed")),("TEXTCOLOR",(0,0),(-1,0),colors.HexColor("#254b3c")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#d7e4dc")),("FONTNAME",(0,1),(-1,-1),"Helvetica"),("FONTSIZE",(0,0),(-1,-1),9),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]));story.append(tbl)
    story.append(Paragraph("Findings and interpretation",styles["CWSection"]));findings=data.get("findings",[])
    if findings:
        for f in findings: story.append(KeepTogether([Paragraph(f.get("title","Finding"),styles["Heading3"]),Paragraph(f.get("explanation",""),styles["CWBody"]),Paragraph("Screening method: "+f.get("method","Not specified"),styles["CWNote"])]))
    else: story.append(Paragraph("No screening findings were returned. This does not guarantee every bill component is correct.",styles["CWBody"]))
    story.append(Paragraph("How ClearWatt checks the bill",styles["CWSection"]));story.append(Paragraph("Daily-normalised historical comparison divides billed units by the number of days in each period and compares the current daily use with the median of previous periods. The median is less sensitive to unusually high or low values. The Modified Z-score uses the median and median absolute deviation to screen for statistical deviations. Thresholds identify records for review; they do not prove a billing error.",styles["CWBody"]))
    for a in (data.get("algorithm_analysis") or {}).get("algorithms",[]):
        name=a.get("name","Algorithm");status=a.get("status","unknown");detail=a.get("note") or a.get("warning") or a.get("reason") or "No additional interpretation available.";result=a.get("current_result") or (f"Current cluster: {a.get('current_cluster')}" if a.get("current_cluster") is not None else (f"Estimated mean shift: {a.get('relative_shift_pct'):.1f}%" if a.get("relative_shift_pct") is not None else ""))
        story.append(Paragraph(f"{name} — {status.replace('_',' ').title()}",styles["Heading3"]));story.append(Paragraph((result+". "+detail).strip(),styles["CWBody"]))
    story.append(Paragraph("Recommended next steps",styles["CWSection"]));steps=data.get("recommendations",[])
    if steps: story.append(Paragraph("<br/>".join(f"{i+1}. {step}" for i,step in enumerate(steps)),styles["CWBody"]))
    story.append(Paragraph("Billing amount limitations",styles["CWSection"]));story.append(Paragraph("This report includes the total amount entered or extracted from the bill. A full charge-level explanation requires itemised energy charges, fixed charges, adjustments, taxes, arrears and applicable tariff details. ClearWatt does not attribute a bill increase to a specific charge when those values have not been verified.",styles["CWBody"]))
    story.append(Paragraph("Limitations and verification",styles["CWSection"]));story.append(Paragraph("OCR may misread bill values. Tariff verification may be unavailable. ML scores are not probabilities; different methods can disagree because they evaluate different patterns. Synthetic benchmark results are not real-world validation. Please verify readings and charges against the official bill and contact the DISCOM if discrepancies remain.",styles["CWBody"]))
    doc.build(story)
    return Response(buf.getvalue(),media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="clearwatt-audit-{audit_id}.pdf"'})
@app.post("/api/ai/explain")
async def explain(req:ExplainIn,db:Session=Depends(get_db)):
    row=db.get(AuditRecord,req.audit_id)
    if not row:raise HTTPException(404,"Bill check not found.")
    evidence=json.loads(row.result_json)
    if not settings.openrouter_api_key:
        return {"explanation":"The AI assistant is not configured right now. Your bill check is still available. " + evidence.get("summary","") + " " + " ".join(evidence.get("notices",[]))}
    body={"model":settings.openrouter_model,"temperature":0.1,"messages":[{"role":"system","content":"You are ClearWatt's consumer electricity bill explainer. Only use the supplied audit evidence. Never invent readings, tariff rules, charges, savings or billing errors. Clearly say when evidence is insufficient. An anomaly is not proof of an incorrect bill. Use simple, respectful language and practical next steps."},{"role":"user","content":req.question+"\nVerified audit evidence JSON:\n"+json.dumps(evidence)}]}
    try:
        async with httpx.AsyncClient(timeout=25) as client:r=await client.post("https://openrouter.ai/api/v1/chat/completions",headers={"Authorization":f"Bearer {settings.openrouter_api_key}","Content-Type":"application/json"},json=body)
        r.raise_for_status();return {"explanation":r.json()["choices"][0]["message"]["content"]}
    except Exception:return {"explanation":"The AI service is temporarily unavailable. Your audit results are unchanged; please use the findings and recommendations shown above."}
@app.post("/api/meter/upload")
async def upload_meter_csv(file:UploadFile=File(...)):
    if Path(file.filename or "").suffix.lower()!=".csv":raise HTTPException(415,"Upload a CSV file containing meter_id, timestamp and reading_kwh columns.")
    raw=await file.read(20*1024*1024+1)
    if len(raw)>20*1024*1024:raise HTTPException(413,"Smart-meter CSV must be 20 MB or smaller.")
    try:df=pd.read_csv(StringIO(raw.decode("utf-8-sig")))
    except Exception:raise HTTPException(422,"CSV could not be read as UTF-8. Please check the file encoding and delimiter.")
    required={"meter_id","timestamp","reading_kwh"}
    if not required.issubset(df.columns):raise HTTPException(422,"Required columns: meter_id, timestamp, reading_kwh. Optional: multiplier.")
    if df.empty:raise HTTPException(422,"The CSV contains no meter readings.")
    df["timestamp"]=pd.to_datetime(df["timestamp"],errors="coerce",utc=True)
    df["reading_kwh"]=pd.to_numeric(df["reading_kwh"],errors="coerce")
    df["meter_id"]=df["meter_id"].astype(str).str.strip()
    invalid_mask=df[["timestamp","reading_kwh"]].isna().any(axis=1) | df["meter_id"].eq("")
    invalid=int(invalid_mask.sum())
    df=df.loc[~invalid_mask].copy()
    negative=int((df["reading_kwh"]<0).sum());df=df[df["reading_kwh"]>=0]
    duplicate_count=int(df.duplicated(["meter_id","timestamp"]).sum());df=df.drop_duplicates(["meter_id","timestamp"],keep="last")
    df=df.sort_values(["meter_id","timestamp"])
    # Readings are treated as cumulative register values. Negative deltas are retained as reset/replacement candidates, not silently corrected.
    df["delta_kwh"]=df.groupby("meter_id")["reading_kwh"].diff()
    resets=int((df["delta_kwh"]<0).sum())
    summaries=[]
    for meter,group in df.groupby("meter_id"):
        deltas=group["delta_kwh"].dropna();positive=deltas[deltas>=0]
        daily_frame=group.loc[group["delta_kwh"]>=0].copy()
        daily_frame["date"]=daily_frame["timestamp"].dt.strftime("%Y-%m-%d")
        daily_values=daily_frame.groupby("date",as_index=False)["delta_kwh"].sum()
        daily_rows=[{"date":str(row.date),"consumption_kwh":round(float(row.delta_kwh),4)} for row in daily_values.itertuples(index=False)]
        try: ml_summary=analyse_daily_meter(daily_rows)
        except (ValueError,TypeError) as exc: ml_summary={"observations":len(daily_rows),"algorithms":[{"name":"Meter ML analysis","status":"error","reason":str(exc)}]}
        summaries.append({"meter_id":meter,"readings":int(len(group)),"period_consumption_kwh":round(float(positive.sum()),3),"negative_register_deltas":int((deltas<0).sum()),"first_reading_at":group["timestamp"].iloc[0].isoformat(),"last_reading_at":group["timestamp"].iloc[-1].isoformat(),"daily_consumption":daily_rows,"algorithm_analysis":ml_summary})
    return {"status":"processed","rows_received":int(len(pd.read_csv(StringIO(raw.decode("utf-8-sig"))))),"valid_rows":int(len(df)),"meter_count":int(df["meter_id"].nunique()),"invalid_rows":invalid,"negative_readings":negative,"duplicate_meter_timestamps":duplicate_count,"possible_register_resets":resets,"meters":summaries,"notice":"Cumulative register drops may indicate a meter reset, replacement, rollover or data issue. They are not automatically treated as faults. Validate units, multipliers and interval semantics before operational use."}

@app.post("/api/evaluate")
def evaluate(req:EvaluationIn):
    try:return evaluate_binary(req.y_true,req.y_pred)
    except ValueError as e:raise HTTPException(422,str(e))
@app.post("/api/meter/isolation-forest")
def meter_iforest(rows:list[dict]):
    try:return {"results":isolation_forest(rows),"warning":"Unsupervised screening; not a probability or ground-truth label."}
    except (ValueError,KeyError,TypeError) as e:raise HTTPException(422,str(e))
@app.post("/api/meter/clusters")
def meter_clusters(payload:dict):
    try:return {"results":cluster_consumers(payload.get("rows",[]),int(payload.get("clusters",3)))}
    except (ValueError,KeyError,TypeError) as e:raise HTTPException(422,str(e))
@app.post("/api/meter/change-point")
def meter_change(payload:dict):
    try:return detect_mean_shift(payload.get("values",[]),int(payload.get("min_segment",3)))
    except (ValueError,TypeError) as e:raise HTTPException(422,str(e))

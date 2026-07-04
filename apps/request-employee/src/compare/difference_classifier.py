PARSER_CRITICAL={"request_no","request_date","customer_name"}

def classify_differences(diffs,pdf_diag,excel_diag):
    out=[]
    pdf_missing=set(pdf_diag.get("missing_fields",[]))
    excel_missing=set(excel_diag.get("missing_fields",[]))
    for d in diffs:
        x=dict(d); field=x.get("field","")
        if field in pdf_missing or field in excel_missing:
            x["difference_type"]="PARSER_FAILURE"
            x["severity"]="ERROR"
        elif field=="line_presence" and (pdf_diag.get("line_count",0)==0 or excel_diag.get("line_count",0)==0):
            x["difference_type"]="PARSER_FAILURE"
            x["severity"]="ERROR"
        else:
            x["difference_type"]="BUSINESS_DIFFERENCE"
        out.append(x)
    return out

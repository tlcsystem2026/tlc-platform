from compare.difference_classifier import classify_differences

def test_parser_failure_classification():
    diffs=[{"field":"request_no","severity":"WARNING","status":"DIFFERENT"}]
    pd={"missing_fields":["request_no"],"line_count":1}
    ed={"missing_fields":[],"line_count":1}
    out=classify_differences(diffs,pd,ed)
    assert out[0]["difference_type"]=="PARSER_FAILURE"
    assert out[0]["severity"]=="ERROR"

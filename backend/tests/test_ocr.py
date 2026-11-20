from app.ocr import extract_fields

def test_conservative_bill_field_extraction():
    text='''Billing Period From: 01/10/2026\nBilling Period To: 30/10/2026\nUnits Consumed: 245 kWh\nNet Amount Payable: Rs. 1,850.00\nPrevious Reading: 1200\nCurrent Reading: 1445'''
    result=extract_fields(text)
    assert result['units']==245
    assert result['amount']==1850
    assert result['meter_reading_previous']==1200
    assert result['meter_reading_current']==1445
    assert result['period_start']=='2026-10-01'
    assert result['period_end']=='2026-10-30'

def test_missing_values_remain_null():
    result=extract_fields('UPPCL electricity bill')
    assert result['units'] is None and result['amount'] is None

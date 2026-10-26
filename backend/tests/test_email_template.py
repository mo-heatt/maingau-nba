from app.email_template import render


def test_html_email_contains_concrete_quote_and_escapes_ai_text():
    material={'headline':'30 GB statt 10 GB','subject':'Ein Angebot','body':'Hallo! <script>alert(1)</script>','benefit_points':['Mehr Daten','<img src=x onerror=alert(1)>']}
    q={'product_id':'P-MO-02','product_name':'Mobil Upgrade','current':{'name':'Mobil S','data_gb':10,'monthly_eur':9.99},'target':{'name':'Mobil M','data_gb':30,'monthly_eur':14.99},'delta_monthly_eur':5,'delta_data_gb':20}
    html=render(material,q,'du','http://127.0.0.1:5173/#customers?customer=MG-100005')
    assert '<script>' not in html and 'onerror=' not in html.replace('&lt;img src=x onerror=alert(1)&gt;','')
    assert '&lt;script&gt;' in html
    for text in ['Mobil S','Mobil M','9,99 €','14,99 €','+5,00 €','+20 GB','role="presentation"','max-width:600px','Für dich ausgewählt']:
        assert text in html
    assert 'Internal' not in html


def test_html_email_uses_formal_salutation_and_rejects_script_url():
    import pytest
    m={'headline':'Ein Angebot','body':'Guten Tag','benefit_points':[]}
    q={'product_id':'P-SV-01','product_name':'Service','current':None,'target':None}
    assert 'Für Sie ausgewählt' in render(m,q,'sie')
    with pytest.raises(ValueError):render(m,q,cta_url='javascript:alert(1)')

"""Deterministic, escaped HTML email around validated AI copy and server-priced quotes."""
import json
import os
from html import escape
from urllib.parse import urlencode, urlparse
from . import database as db

HERO='https://cdn0.scrvt.com/7005d26a0638ef2e9656e7be7c45a3cb/42017dbf0679e0d2/d20a0c485cc0/v/0d3e42c30d2e/Mobilfunk-Handytarife-Maingau.jpeg?nowebp=1'


def eur(n):return f'{float(n):,.2f}'.replace(',','X').replace('.',',').replace('X','.')+' €'


def render(material,quote,tone='du',cta_url='https://www.maingau-energie.de/mobilfunk',article=None,informational=False,language='de'):
    from .communication import language as normalise
    lang=normalise(language);en=lang=='en'
    t=lambda de,english:english if en else de
    e=lambda value:escape(str(value),quote=True)
    money=lambda n:('€'+f'{float(n):,.2f}') if en else eur(n)
    if urlparse(cta_url).scheme not in ['http','https']:raise ValueError('Email CTA must be an HTTP(S) URL')
    target=quote.get('target') or {};current=quote.get('current') or {}
    service=quote['product_id']=='P-SV-01'
    title=material.get('headline') or material.get('subject') or t('Ein passendes Angebot','A suitable next step')
    paragraphs=''.join('<p style="margin:0 0 18px;font-size:16px;line-height:1.8;color:#52677f;">'+e(text).replace('\n','<br>')+'</p>' for text in material.get('body','').split('\n\n') if text.strip())
    benefits=''.join('<tr><td width="26" valign="top" style="color:#16836a;padding:7px 0;">&#10003;</td><td style="padding:7px 0;font-size:15px;line-height:1.6;color:#355b80;">'+e(text)+'</td></tr>' for text in material.get('benefit_points',[]))
    def side(value):
        rows='<strong style="font-size:18px;color:#183d67;">'+e(value.get('name',t('Konditionen prüfen','Check terms')))+'</strong>'
        if value.get('data_gb') is not None:rows+='<br>'+e(f"{value['data_gb']:g}")+' GB'
        if value.get('monthly_eur') is not None:rows+='<br>'+e(money(value['monthly_eur']))+' / '+t('Monat','month')
        if value.get('unit_eur_kwh') is not None:rows+='<br>'+e(str(value['unit_eur_kwh']) if en else str(value['unit_eur_kwh']).replace('.',','))+' € / kWh'
        if value.get('base_eur_month') is not None:rows+='<br>'+e(money(value['base_eur_month']))+' '+t('Grundpreis / Monat','base fee / month')
        return rows
    comparison=''
    if current:
        comparison=f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #dce5ef;margin-top:24px;"><tr><td width="50%" valign="top" style="padding:23px 10px 15px 0;"><p>{t("AKTUELL","CURRENT")}</p>{side(current)}</td><td width="50%" valign="top" style="padding:23px 0 15px 10px;"><p>{t("VORSCHLAG","PROPOSED")}</p>{side(target)}</td></tr></table>'
    delta=''
    if quote.get('delta_monthly_eur') is not None:
        n=quote['delta_monthly_eur'];delta=('<span>'+('+' if n>=0 else '−')+e(money(abs(n)))+' / '+t('Monat','month')+'</span>')
        if quote.get('delta_data_gb') is not None:delta+='<span style="float:right;font-weight:bold;">+'+e(f"{quote['delta_data_gb']:g}")+' GB</span>'
        delta='<div style="padding:16px 0;border-top:1px solid #dce5ef;">'+delta+'</div>'
    allowance=('<span style="font-size:64px;font-weight:bold;color:#0d3562;">'+e(f"{target['data_gb']:g}")+'</span> GB') if target.get('data_gb') is not None else ''
    price=''
    if target.get('monthly_eur') is not None:price='<p style="font-size:27px;">'+e(money(target['monthly_eur']))+' <span style="font-size:12px;">/ '+t('Monat','month')+'</span></p>'
    elif target.get('one_off_eur') is not None:price='<p style="font-size:27px;">'+e(money(target['one_off_eur']))+' <span style="font-size:12px;">'+t('einmalig','one-off')+'</span></p>'
    article_block=''
    if article and urlparse(article['url']).scheme=='https':
        article_block=f'<div style="padding:18px;background:#f4f7fc;border-left:3px solid #ffe500;margin:20px 0;"><strong>{e(article["title"])}</strong><p style="font-size:11px;">{t("Quelle: MAINGAU","Source: MAINGAU · original article in German")} · {e(article.get("published_at") or t("Datum nicht angegeben","Date not provided"))}</p><a href="{e(article["url"])}" target="_blank">{t("Originalbeitrag lesen","Read the original article")} &rarr;</a></div>'
    photo=('<tr><td><img src="'+HERO+'" width="600" alt="'+t('MAINGAU Mobilfunk – Themenbild','MAINGAU mobile services')+'" style="display:block;width:100%;height:auto;max-height:240px;object-fit:cover;border:0;"></td></tr>') if quote['product_id'].startswith('P-MO') else ''
    salutation='Selected for you' if en else ('Für dich ausgewählt' if tone=='du' else 'Für Sie ausgewählt')
    heading=t('ZUM ORIGINALBEITRAG','READ THE ORIGINAL ARTICLE') if informational else t('DER PASSENDE NÄCHSTE SCHRITT','YOUR NEXT STEP')
    cta=t('Artikel lesen','Read the article') if informational else t('Service ansehen','View service help') if service else t('Dieses Angebot ansehen','View this offer')
    disclaimer=t('Informationsentwurf. Details und Veröffentlichung auf der verlinkten Originalseite prüfen.','Information draft. Check details and publication on the original page.') if informational else t('Servicevorschau. Kein Verkauf und keine Nachricht versendet.','Service preview. No sale or message sent.') if service else t('Demo-Tarif aus bereitgestellten Daten. Kein Vertragsabschluss. Laufzeit, Gebühren und Verfügbarkeit sind noch zu prüfen.','Demo tariff from supplied data. No contract is concluded. Term, fees and availability still require verification.')
    target_name=t('Hilfe zu Ihrem Anliegen','Help with your issue') if service else target.get('name') or quote['product_name']
    team='Your' if en else ('Dein' if tone=='du' else 'Ihr')
    return f'''<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="referrer" content="no-referrer"><title>{e(material.get('subject') or title)}</title><style>@media only screen and (max-width:620px){{.email-pad{{padding:26px 22px!important}}.outer-pad{{padding:12px 0!important}}.email-headline{{font-size:29px!important}}.offer-pad{{padding:25px 22px!important}}}}@media(prefers-color-scheme:dark){{.email-canvas{{color-scheme:light}}}}</style></head><body style="margin:0;padding:0;background:#edf2f8;font-family:Arial,Helvetica,sans-serif;"><div style="display:none;max-height:0;overflow:hidden;opacity:0;">{e(title)}&nbsp;&#847;</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#edf2f8;"><tr><td class="outer-pad" align="center" style="padding:32px 16px;">
<table role="presentation" class="email-canvas" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#fff;border:1px solid #dfe6ef;border-radius:12px;overflow:hidden;">
<tr><td style="background:#002657;padding:27px 34px;border-bottom:4px solid #ffe500;"><span style="color:#fff;font-size:28px;font-weight:bold;letter-spacing:-1px;">MAINGAU</span><span style="display:inline-block;background:#ffe500;color:#002657;border-radius:50%;font-size:22px;font-weight:bold;line-height:24px;width:24px;text-align:center;margin-left:4px;">+</span><span style="display:block;color:#a8bad1;font-size:10px;letter-spacing:1.7px;margin-top:11px;">{t('ENERGIE. VERBINDUNG. DEIN ALLTAG.','ENERGY. CONNECTION. YOUR EVERYDAY.')}</span></td></tr>
{photo}<tr><td class="email-pad" style="padding:35px 36px 19px;"><p style="font-size:10px;text-transform:uppercase;letter-spacing:1.8px;color:#8197b0;margin:0 0 15px;">{e(salutation)}</p><h1 class="email-headline" style="margin:0 0 24px;font-size:36px;line-height:1.17;color:#0a315d;">{e(title)}</h1>{paragraphs}{article_block}{('<table role="presentation" width="100%" cellspacing="0" cellpadding="0">'+benefits+'</table>') if benefits else ''}</td></tr>
<tr><td class="email-pad" style="padding:10px 36px 33px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7fc;border:1px solid #dfe7f2;border-radius:9px;"><tr><td class="offer-pad" style="padding:28px;"><p style="font-size:10px;letter-spacing:1.4px;color:#8196af;margin:0 0 10px;">{heading}</p><h2 style="font-size:25px;margin:0 0 21px;color:#173f6c;">{e(target_name)}</h2>{allowance}{price}{comparison}{delta}<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:18px;"><tr><td align="center" bgcolor="#ffe500" style="border-radius:6px;"><a href="{e(cta_url)}" target="_blank" style="display:block;padding:17px 18px;font-size:14px;font-weight:bold;text-decoration:none;color:#002657;">{cta} &rarr;</a></td></tr></table><p style="font-size:10px;line-height:1.7;color:#899cb2;">{disclaimer}</p></td></tr></table></td></tr>
<tr><td class="email-pad" style="padding:0 36px 30px;"><p style="font-size:14px;color:#48698e;">{team} MAINGAU Team</p></td></tr>
<tr><td style="padding:24px 32px;background:#f8fafd;border-top:1px solid #e5ebf4;text-align:center;"><b>MAINGAU Energie</b><p style="font-size:10px;line-height:1.8;color:#98a8bb;">{t('Hackathon-Demo · synthetische Daten · nicht versendet.','Hackathon demo · synthetic data · not sent.')}<br>{t('Diese Vorschau enthält keinen verbindlichen Tarif und kein Versand-Abonnement.','This preview does not create a binding tariff or mailing subscription.')}</p></td></tr></table>
<p style="font-size:10px;color:#a1afc0;text-align:center;">{t('Ein Angebot, das zur Situation passt.','A next step that fits your situation.')}</p></td></tr></table></body></html>'''


def for_draft(draft):
    identifier=draft['decision_id']
    kind=identifier.split(':',1)[0]
    if kind not in ['outreach','newsletter']:return None
    try:mid=int(identifier.split(':',1)[1])
    except ValueError:return None
    table='outreach_materials' if kind=='outreach' else 'newsletter_materials'
    with db.connect() as c:row=c.execute('SELECT * FROM '+table+' WHERE id=? AND customer_id=?',(mid,draft['customer_id'])).fetchone()
    if not row or row['status']!='validated':return None
    p=json.loads(row['payload']);material=p['material']
    if material.get('subject')!=draft['subject'] or material['body']!=draft['body']:return None
    base=os.getenv('NBA_PUBLIC_APP_URL','http://127.0.0.1:5173').rstrip('/')
    url=base+'/#customers?'+urlencode({'customer':draft['customer_id'],'material':mid})
    article=p.get('article')
    informational=kind=='newsletter' and p.get('mode')=='informational'
    if informational:url=article['url']
    from .communication import language_errors
    if language_errors(material,p.get('language') or p.get('dossier',{}).get('language','de')):return None
    return render(material,p['quote'],p.get('tone') or p['dossier']['tone'],url,article,informational,p.get('language') or p.get('dossier',{}).get('language','de'))

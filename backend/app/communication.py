"""Customer communication language is independent of the operator UI and German tone."""
import re

VERSION='communication-en-de-v1'


def language(value):
    code=str(value or 'de').strip().lower().replace('_','-').split('-')[0]
    if code not in ('de','en'):raise ValueError('Unsupported customer communication language: '+code)
    return code


def instruction(value,tone):
    code=language(value)
    if code=='en':
        return ('LANGUAGE CONTRACT: Write EVERY headline, subject, message, call section and internal brief in English. '
                'Source records and product names may be German; they do not change the output language. '
                'Keep product names and evidence quotes unchanged. German Du/Sie examples elsewhere apply ONLY to German output; '
                'do not copy them into English. Use a '+('warm conversational' if tone=='du' else 'polite professional')+
                ' English register, addressing the customer as you/your. Never insert German greetings or sentences.')
    return ('LANGUAGE CONTRACT: Write the communication in German. Use '+('du/dir/dich/dein' if tone=='du' else 'Sie/Ihnen/Ihr')+
            ' consistently in customer-facing sections. Preserve product names and exact evidence quotes.')


_DE=set('ich wir dir dich dein deine deinem deinen ihnen ihr ihre ihren ihrem sie für und nicht ist mit einen einem das der die bitte können möchten gerne gern helfen anliegen klären beschwerde mehr daten'.split())
_EN=set('the you your we our with and not is this that please can would help issue resolve more data to for'.split())


def language_errors(material,value):
    """Conservative EN/DE guard, not a general-purpose language detector.

    Names, evidence and source metadata are not classified. Short ambiguous text
    is left to the language contract rather than blocking valid product names.
    """
    code=language(value)
    if hasattr(material,'model_dump'):material=material.model_dump()
    fields=[]
    for key in ('headline','subject','body','opening','offer_pitch','closing'):
        if material.get(key):fields.append(material[key])
    fields.extend(material.get('benefit_points',[]));fields.extend(material.get('discovery_questions',[]))
    for objection in material.get('objections',[]):fields.extend([objection.get('concern',''),objection.get('response','')])
    for text in fields:
        words=set(re.findall(r"[a-zäöüß]+",text.lower()));de=len(words&_DE);en=len(words&_EN)
        wrong=(de>=2 and de>en+1) if code=='en' else (en>=3 and en>de+2)
        if code=='en' and re.match(r'\s*(?:Hallo\b|Guten Tag\b|Für (?:dich|Sie)\b)',text):wrong=True
        if wrong:return ['Copy does not respect customer language: '+('English' if code=='en' else 'German')]
    return []

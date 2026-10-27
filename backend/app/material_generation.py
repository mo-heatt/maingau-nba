"""Bounded copy repair; never re-run product selection or weaken validation."""
from . import ai_nba

MAX_ATTEMPTS=3  # Initial generation plus at most two repairs.


def generate(schema,prompt,packet,validate):
    result={'material':None,'errors':[],'error':None,'usage':[],'attempts':[],'max_attempts':MAX_ATTEMPTS,'status':'failed'}
    language=packet.get('language') if isinstance(packet,dict) else None
    language_name={'de':'German','en':'English'}.get(str(language).lower() if language else '')
    for number in range(1,MAX_ATTEMPTS+1):
        request=dict(packet)
        if language_name:request['required_output_language']=language_name
        if result['material'] is not None:
            repair='Correct every listed error in the complete response.'
            if language_name:repair+=' Rewrite the COMPLETE response in '+language_name+'; every headline, subject, sentence and list item must be '+language_name+'. Keep recognised product names unchanged.'
            repair+=' Preserve verified facts and the selected NBA; do not change product, channel, language, tone or prices.'
            request.update(previous_material=result['material'].model_dump(),errors_to_fix=result['errors'],repair_instruction=repair)
        try:
            material,usage=ai_nba.complete(schema,prompt,request)
        except ai_nba.ProviderError as exc:
            result['error']=str(exc)
            result['attempts'].append({'number':number,'status':'failed','errors':['AI provider could not return usable copy']})
            break
        result['usage'].append(usage)
        errors=list(dict.fromkeys(validate(material)))
        result.update(material=material,errors=errors,status='blocked' if errors else 'validated')
        result['attempts'].append({'number':number,'status':result['status'],'errors':errors})
        if not errors:break
    if result['error']:result['status']='failed'
    return result


def explain(errors,tone):
    explanations=[]
    for error in errors:
        if 'customer language' in error:
            title='Wrong customer language';message='The draft was not written in the customer’s preferred language. Regenerate the text in that language.'
        elif 'tone' in error or error in ('Use Du tone','Use Sie tone'):
            title='Mixed forms of address'
            message=f'The customer uses {"Du" if tone=="du" else "Sie"}, but parts of the draft use the other form of address.'
        elif 'Evidence' in error or 'cite' in error:
            title='Source could not be verified';message='A claim or reference in the draft does not match the supplied source facts.'
        elif any(word in error for word in ('numeric','Savings','price','monthly price','Date','contact time')):
            title='Unsupported offer detail';message='The draft includes a price, saving, quantity or timing that the supplied data does not support.'
        elif any(word in error for word in ('call brief','Call script')):
            title='Call script needs correction';message='The internal customer brief and the words spoken to the customer are not separated correctly, or a required call section is missing.'
        elif 'changed' in error or 'stale' in error:
            title='Customer context changed';message='The decision or channel permissions changed. Refresh the customer before generating again.'
        else:
            title='Content check failed';message=error
        detail={'title':title,'message':message}
        if detail not in explanations:explanations.append(detail)
    return explanations

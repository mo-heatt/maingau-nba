export const isEnglish=(language:string)=>language.toLowerCase().replace('_','-').split('-')[0]==='en';
export const toneLabel=(language:string,tone:string)=>isEnglish(language)?(tone==='du'?'Informal':'Formal'):(tone==='du'?'Du':'Sie');
export const englishProductDescriptions:Record<string,string>={
 'P-EN-01':'An electricity tariff with flexible pricing.',
 'P-EN-02':'An electricity tariff with a 24-month price guarantee.',
 'P-EN-03':'An electricity tariff for homes with a heat pump.',
 'P-EN-04':'Gas for your home. Check the tariff terms.',
 'P-EN-05':'A dynamic electricity tariff. Check technical requirements.',
 'P-MO-01':'Mobile service with a suitable data package.',
 'P-MO-02':'More mobile data by moving to the next tariff tier.',
 'P-MO-03':'An additional SIM card for another person in the household.',
 'P-IN-01':'DSL or fibre internet. Check availability at your address.',
 'P-SL-01':'Connected home energy management.',
 'P-SL-02':'Optimise control of your existing home battery.',
 'P-SL-03':'Connect your wallbox to your energy management system.',
 'P-SH-01':'A balcony solar system for generating electricity.',
 'P-SH-02':'A wallbox for charging at home.',
 'P-SH-03':'Smart thermostats for heating control.',
 'P-SH-04':'Smart plugs for a connected home.',
 'P-AS-01':'Charging on the road with MAINGAU Autostrom.',
 'P-SV-01':'Let’s find a suitable solution for your open issue.',
};

import {Smartphone,Wifi,Zap,PlugZap,Headphones,House} from 'lucide-react';
// Customer-facing translations of the synthetic catalogue descriptions.
// Prices and eligibility are deliberately left to the verified product pages.
export const productDescriptions:Record<string,string>={
 'P-EN-01':'Stromtarif mit flexiblem Preis.',
 'P-EN-02':'Stromtarif mit 24 Monaten Preisgarantie.',
 'P-EN-03':'Stromtarif für Haushalte mit Wärmepumpe.',
 'P-EN-04':'Gasversorgung für zu Hause. Konditionen im Tarifvergleich prüfen.',
 'P-EN-05':'Dynamischer Stromtarif. Technische Voraussetzungen prüfen.',
 'P-MO-01':'Mobilfunk für unterwegs. Das passende Datenpaket im Tarifvergleich finden.',
 'P-MO-02':'Mehr Datenvolumen durch Wechsel in die nächste Tarifstufe.',
 'P-MO-03':'Eine zusätzliche SIM-Karte für weitere Personen im Haushalt.',
 'P-IN-01':'Internet über DSL oder Glasfaser. Verfügbarkeit an der Anschlussadresse prüfen.',
 'P-SL-01':'Vernetztes Energiemanagement für zu Hause.',
 'P-SL-02':'Die Steuerung des vorhandenen Heimspeichers optimieren.',
 'P-SL-03':'Die Wallbox in das Energiemanagement einbinden.',
 'P-SH-01':'Ein Balkonkraftwerk für die eigene Stromerzeugung.',
 'P-SH-02':'Eine Wallbox für das Laden zu Hause.',
 'P-SH-03':'Smarte Thermostate für die Heizungssteuerung.',
 'P-SH-04':'Smarte Steckdosen für das vernetzte Zuhause.',
 'P-AS-01':'Unterwegs laden mit MAINGAU Autostrom.',
 'P-SV-01':'Gemeinsam eine passende Lösung für das offene Anliegen finden.',
};

const MOBILE_IMAGE='https://cdn0.scrvt.com/7005d26a0638ef2e9656e7be7c45a3cb/42017dbf0679e0d2/d20a0c485cc0/v/0d3e42c30d2e/Mobilfunk-Handytarife-Maingau.jpeg?nowebp=1';
const ENERGY_IMAGE='https://cdn0.scrvt.com/7005d26a0638ef2e9656e7be7c45a3cb/0963389c2cf5b953/a5827253d198/v/9f6adfa945cc/Energiespartipps-Strom-gas-sparen?nowebp=1';
export function destination(id:string){
 if(id.startsWith('P-MO'))return {url:'https://www.maingau-energie.de/mobilfunk',label:'Mobilfunktarife ansehen',category:'Mobilfunk',Icon:Smartphone,image:MOBILE_IMAGE};
 if(id.startsWith('P-IN'))return {url:'https://www.maingau-energie.de/internet',label:'Internet entdecken',category:'Internet',Icon:Wifi,image:null};
 if(id.startsWith('P-EN'))return {url:'https://www.maingau-energie.de/'+(id==='P-EN-04'?'gas':'strom'),label:'Tarife & Konditionen ansehen',category:'Energie',Icon:Zap,image:ENERGY_IMAGE};
 if(id.startsWith('P-AS'))return {url:'https://www.maingau-energie.de/e-mobilitaet/autostrom',label:'Autostrom entdecken',category:'Elektromobilität',Icon:PlugZap,image:null};
 if(id.startsWith('P-SV'))return {url:'https://www.maingau-energie.de/service',label:'Zum MAINGAU Service',category:'Service',Icon:Headphones,image:null};
 return {url:'https://www.maingau-energie.de/'+(id.startsWith('P-SL')?'smart-living':'onlineshop'),label:'Produkte entdecken',category:id.startsWith('P-SL')?'Smart Living':'Onlineshop',Icon:House,image:null};
}

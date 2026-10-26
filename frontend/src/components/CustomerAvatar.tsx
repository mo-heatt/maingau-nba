export default function CustomerAvatar({id,large=false}:{id:string;large?:boolean}){
 const variant=Number(id.replace(/\D/g,''))%4;
 return <span className={'customer-avatar avatar-tone-'+variant+(large?' large':'')} aria-hidden="true"><svg viewBox="0 0 48 48" fill="none"><circle cx="24" cy="18" r="7" stroke="currentColor" strokeWidth="1.6"/><path d="M11 39c0-8 5-13 13-13s13 5 13 13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg></span>
}

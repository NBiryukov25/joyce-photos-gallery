// No provider credentials belong in this module. The session token stays in memory.
export class ApiClient {
  constructor(base, network=(...args)=>fetch(...args)) {this.base=base.replace(/\/$/,'');this.network=network;this.accessToken='';this.csrf='';this.blobs=new Map();}
  async request(path,options={},binary=false) {
    const headers={...options.headers};
    if(this.accessToken)headers.Authorization=`Bearer ${this.accessToken}`;
    if(options.method && this.csrf)headers['X-Angle-Pack-Token']=this.csrf;
    let response;
    try{response=await this.network(this.base+path,{...options,headers,credentials:'omit',signal:AbortSignal.timeout(120000)});}
    catch{throw new Error('Backend unavailable. Check the Render URL and connection; a sleeping service may take a minute to wake. Check Saved sessions before submitting again.');}
    if(response.status===401){this.accessToken='';this.csrf='';throw Object.assign(new Error('Sign in to ANGLE PACK. Your session may have expired.'),{status:401});}
    if(!response.ok){const data=await response.json().catch(()=>({}));throw Object.assign(new Error(response.status===404?'Session or file expired / not found. Temporary files may disappear after a restart.':data.error||`Request failed (${response.status}).`),{status:response.status});}
    return binary?response.blob():response.json();
  }
  async login(password){const result=await this.request('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password})});this.accessToken=result.accessToken;}
  async blobUrl(path){if(!this.blobs.has(path))this.blobs.set(path,this.request(path,{},true).then(blob=>URL.createObjectURL(blob)).catch(e=>{this.blobs.delete(path);throw e;}));return this.blobs.get(path);}
  invalidate(path){this.blobs.get(path)?.then(url=>URL.revokeObjectURL(url)).catch(()=>{});this.blobs.delete(path);}
  clear(){for(const value of this.blobs.values())value.then(url=>URL.revokeObjectURL(url)).catch(()=>{});this.blobs.clear();this.accessToken='';this.csrf='';}
}

export function uploadForm(references,spec){const form=new FormData();for(const ref of references)form.append('references',ref.file,ref.name);form.append('spec',JSON.stringify(spec));return form;}

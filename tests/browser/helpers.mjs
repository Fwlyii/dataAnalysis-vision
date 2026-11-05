import{existsSync}from'node:fs';import{mkdir}from'node:fs/promises';import{resolve}from'node:path';
export const baseURL=process.env.BASE_URL||'http://127.0.0.1:8838/';
export const chromiumPath=process.env.CHROMIUM_PATH||(existsSync('/snap/bin/chromium')?'/snap/bin/chromium':undefined);
for(const p of ['artifacts/qa/after','artifacts/qa/iterations','artifacts/qa/downloads'])await mkdir(resolve(p),{recursive:true});
export async function screenshot(page,options){if(process.env.QA_SCREENSHOTS==='1')return page.screenshot(options);}

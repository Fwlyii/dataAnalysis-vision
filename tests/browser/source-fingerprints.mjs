import{readFile,readdir}from'node:fs/promises';import{createHash}from'node:crypto';
async function walk(dir){const entries=await readdir(dir,{withFileTypes:true});return(await Promise.all(entries.map(e=>e.isDirectory()?walk(dir+'/'+e.name):[dir+'/'+e.name]))).flat();}
export async function fingerprints(){
 const files=[...(await readdir('app')).filter(n=>/\.(html|css)$/.test(n)&&n!=='visual-coverage.json').map(n=>'app/'+n),...await walk('app/src'),...await walk('app/assets'),...await walk('app/data'),...await walk('reports/figures/publication'),...await walk('reports/figures/code_generation'),'scripts/system/build_web_app.py','scripts/system/build_demo_evidence.py','reports/code_generation/conditions.csv'].filter((p,i,a)=>a.indexOf(p)===i);
 const result={};for(const f of files){let b=await readFile(f);if(f.endsWith('.html'))b=Buffer.from(b.toString().replace(/\?v=[a-f0-9]+/g,'?v=BUILD'));if(f.endsWith('.css'))b=Buffer.from(b.toString().replace(/[ \t]+$/gm,''));result[f]=createHash('sha256').update(b).digest('hex');}return result;
}

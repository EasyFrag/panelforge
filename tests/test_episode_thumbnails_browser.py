"""User-run DOM checks with a fake cover API, no generation."""
import os
from pathlib import Path
import unittest
from tests.test_media_analysis_browser import MediaAnalysisBrowserTest, STATIC


class ThumbnailBrowserTest(unittest.TestCase):
    run_browser = MediaAnalysisBrowserTest.run_browser

    def test_cover_is_first_and_editing_never_calls_scene_endpoints(self):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        source = (STATIC / "index.html").read_text(encoding="utf8")
        dialog = '<dialog id="episode-thumbnail-dialog"' + source.split('<dialog id="episode-thumbnail-dialog"', 1)[1].split('</dialog>', 1)[0] + '</dialog>'
        badge_dialog = '<dialog id="episode-thumbnail-badge-dialog"' + source.split('<dialog id="episode-thumbnail-badge-dialog"', 1)[1].split('</dialog>', 1)[0] + '</dialog>'
        checks = r"""
(async()=>{try{
 const check=(ok,message)=>{if(!ok)throw Error(message);};
 const settle=()=>new Promise(resolve=>setTimeout(resolve,0));
 const el=name=>document.getElementById('episode-thumbnail-'+name);
 const calls=[];let finish=null;
 const geometry={x:290,y:1150,width:501,height:161,canvas:{width:1080,height:1440},position:{x:290/579*100,y:1150/1279*100},default_position:{x:290/579*100,y:1150/1279*100}};
 let current={episode_id:'episode-one',group_id:'series-one',revision:0,status:'missing',title:'GLOW UP',number:1,
   asset_id:null,templates:[],template:null,qwen_available:true,default_reference_ids:['pechette'],
   output_format:{width:1080,height:1440,aspect_ratio:'3:4'},
   references:[{id:'pechette',name:'Pêchette',kind:'character',asset_id:'peach'}, ...Array.from({length:15},(_,i)=>({id:'extra-'+i,name:'Autre '+i,kind:'character',asset_id:'image-'+i}))]};
 const request=async(url,options)=>{
   calls.push({url,options});
   if(!options)return structuredClone(current);
   const body=JSON.parse(options.body);
   if(url.endsWith('/archive')){
     const id=url.split('/templates/')[1].split('/')[0];
     current={...current,templates:current.templates.map(t=>t.id===id?{...t,archived_at:body.archived?'2026-09-24':null,revision:t.revision+1}:t)};
     return structuredClone(current);
   }
   if(url.endsWith('/badge')){
     current={...current,revision:current.revision+1,asset_id:'moved-cover',badge:{...geometry,position:body.position}};
     return structuredClone(current);
   }
   await new Promise(resolve=>{finish=resolve;});
   current={...current,revision:current.revision+1,status:'ready',title:body.title,number:body.number,
     asset_id:'poster-'+body.number,asset_format:{width:1080,height:1440,aspect_ratio:'3:4'},series_template_id:'cover-test',template_id:'cover-test',
     badge:structuredClone(geometry),
     templates:[{id:'cover-test',group_id:'series-one',title:body.title,title_mode:'artwork',asset_id:'master',output_format:{width:1080,height:1440,aspect_ratio:'3:4'},created_at:'2026-09-24T12:00:00Z',episode_count:1,series_count:1,can_archive:false,revision:0},
       {id:'cover-unused',group_id:'series-one',title:'Essai Citron',title_mode:'artwork',asset_id:'old-master',created_at:'2026-09-24T11:00:00Z',episode_count:0,series_count:0,can_archive:true,revision:0},
       {id:'cover-external',group_id:'other-series',title:'Autre série',title_mode:'artwork',asset_id:'other-master',created_at:'2026-09-24T13:00:00Z',episode_count:1,series_count:1,can_archive:false,revision:0}]};
   return structuredClone(current);
 };
 const ui=PanelForgeEpisodeThumbnails.create({request});
 const container=document.getElementById('cards');
 ui.mount(container,{episode_id:'episode-one'});await settle();
 check(container.firstElementChild.classList.contains('episode-thumbnail-card'),'cover precedes scene 1');
 check(container.querySelector('#scene-one'),'scene retained');
 const modify=[...container.querySelectorAll('button')].find(b=>b.textContent==='Modifier le modèle');
 modify.click();check(el('dialog').open,'opens accessible dialog');
 check(el('source').value==='generate','first series defaults to Qwen');
 check(el('format-note').textContent.includes('1080 × 1440')&&el('format-note').textContent.includes('3:4'),'grid export format clearly shown');
 check(el('references').querySelector('input').checked,'current character preselected');
 const extra=el('references').querySelectorAll('.episode-thumbnail-reference')[1];
 extra.querySelector('input').checked=true;extra.querySelector('input').dispatchEvent(new Event('change'));
 extra.querySelector('select').value='background';extra.querySelector('select').dispatchEvent(new Event('change'));
 check(el('reference-count').textContent.includes('2 / 16'),'more references supported with clear count');
 check(el('reference-count').textContent.includes('1 à l’arrière-plan'),'supporting role counted');
 el('title-style').value='cinema';el('title-style').dispatchEvent(new Event('change'));
 check(el('title-sample').dataset.style==='cinema','typography preview updates');
 el('number').value='3';el('submit').click();el('submit').click();await settle();
 check(calls.filter(c=>c.options).length===1,'double click queues once');
 const firstBody=JSON.parse(calls.find(c=>c.options).options.body);
 check(firstBody.reference_roles['extra-0']==='background'&&firstBody.reference_roles.pechette==='foreground','explicit per-image hierarchy');
 check(firstBody.title_style==='cinema','title styling submitted without a writer call');
 check(el('submit').disabled,'button disabled while preparing');
 finish();await settle();await settle();
 check(!el('dialog').open,'successful edit closes dialog');
 check(container.querySelector('.episode-thumbnail-status').textContent.includes('Prête'),'ready state');
 check(!container.querySelector('.episode-thumbnail-download').hidden,'separate download available');
 check(container.textContent.includes('1080 × 1440'),'card reports real export dimensions');
 modify.click();check(el('source').value==='series','reuses series model');
 check(el('title').disabled,'raster title preserved');
 el('number').value='4';el('submit').click();await settle();
 const body=JSON.parse(calls.filter(c=>c.options).at(-1).options.body);
 check(body.source==='series'&&body.number===4,'only applies template and number');
 finish();await settle();await settle();
 modify.click();
 check(el('gallery-items').children.length===2,'gallery defaults to current series');
 check(el('gallery-items').firstElementChild.dataset.templateId==='cover-test','current template pinned first');
 check(el('gallery-items').firstElementChild.querySelector('button:last-child').disabled,'used model protected');
 el('gallery-filter').value='unused';el('gallery-filter').dispatchEvent(new Event('change'));
 check(el('gallery-items').children.length===1&&el('gallery-items').textContent.includes('Essai Citron'),'unused filter');
 const beforeChoice=calls.length;
 el('gallery-items').querySelector('.episode-thumbnail-model-choice').click();
 check(calls.length===beforeChoice&&el('source').value==='library','selecting an image does not generate or apply');
 el('gallery-items').querySelector('.episode-thumbnail-model > button:last-child').click();await settle();await settle();
 check(current.templates.find(t=>t.id==='cover-unused').archived_at,'unused model trashed');
 el('gallery-filter').value='trash';el('gallery-filter').dispatchEvent(new Event('change'));
 check(el('gallery-items').textContent.includes('Restaurer'),'trash offers restore');
 el('gallery-items').querySelector('.episode-thumbnail-model > button:last-child').click();await settle();await settle();
 check(!current.templates.find(t=>t.id==='cover-unused').archived_at,'restored without generation');
 el('gallery-filter').value='all';el('gallery-filter').dispatchEvent(new Event('change'));
 check(el('gallery-items').children.length===3,'other series available explicitly');
 el('gallery-search').value='citron';el('gallery-search').dispatchEvent(new Event('input'));
 check(el('gallery-items').children.length===1,'title search');
 el('close').click();
 const move=[...container.querySelectorAll('button')].find(b=>b.textContent==='Déplacer le bandeau');
 check(!move.hidden,'ready thumbnail exposes manual badge positioning');move.click();
 const badge=name=>document.getElementById('episode-thumbnail-badge-'+name);
 check(badge('dialog').open,'layout editor opens');
 check(badge('save').disabled,'save waits for both preview images');
 badge('background').dispatchEvent(new Event('load'));badge('image').dispatchEvent(new Event('load'));
 check(!badge('save').disabled,'preview is usable before saving');
 badge('handle').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowUp',bubbles:true}));
 check(Number(badge('y').value)<geometry.position.y,'keyboard can adjust badge');
 const rect=badge('stage').getBoundingClientRect();
 badge('handle').setPointerCapture=()=>{};
 const beforeDrag=Number(badge('x').value);
 badge('handle').dispatchEvent(new PointerEvent('pointerdown',{pointerId:1,button:0,clientX:rect.left+60,clientY:rect.top+200,bubbles:true}));
 badge('handle').dispatchEvent(new PointerEvent('pointermove',{pointerId:1,clientX:rect.left+80,clientY:rect.top+160,bubbles:true}));
 badge('handle').dispatchEvent(new PointerEvent('pointerup',{pointerId:1,bubbles:true}));
 check(Number(badge('x').value)>beforeDrag,'pointer drag moves the badge');
 badge('dialog').querySelector('[data-badge-preset="8"]').click();
 check(Number(badge('y').value)===8,'upper preset uncovers lower title');
 badge('x').value='20';badge('x').dispatchEvent(new Event('input'));
 badge('save').click();badge('save').click();await settle();await settle();
 const badgeCalls=calls.filter(c=>c.url.endsWith('/badge'));
 check(badgeCalls.length===1,'manual placement double click saved once');
 const badgeBody=JSON.parse(badgeCalls[0].options.body);
 check(badgeBody.position.x===20&&badgeBody.position.y===8&&badgeBody.remember_series,'position and future-series preference submitted');
 check(!badge('dialog').open&&container.querySelector('.episode-thumbnail-preview img').src.includes('moved-cover'),'updated cover displayed');
 move.click();check(Number(badge('y').value)===8,'position retained on reopening');badge('close').click();
 check(calls.every(c=>c.url.includes('/thumbnail')),'no scene, prompt or video endpoint called');
 check(container.children.length===2,'no duplicate scene or cover card');
 ui.close();document.getElementById('result').textContent='PASS';
}catch(error){document.getElementById('result').textContent='FAIL: '+error.stack;}})();
"""
        html = ('<meta charset="utf-8"><pre id="result">PENDING</pre><div id="cards"><article id="scene-one">Scène 1</article></div>'
                + dialog + badge_dialog + '<style>' + (STATIC / 'episode-thumbnails.css').read_text(encoding='utf8') + '</style><script>' + (STATIC / 'episode-thumbnail-layout.js').read_text(encoding='utf8') + '</script><script>' + (STATIC / 'episode-thumbnails.js').read_text(encoding='utf8')
                + '</script><script>' + checks + '</script>')
        self.run_browser(browsers[-1], html)

"use strict";
const CACHE="panelforge-mobile-20260928-3";
const SHELL=["/","/app.css?v=20260928.mobile2","/thermal.js?v=20260928.mobile2","/app.js?v=20260928.mobile3","/icon.svg","/icon-192.png","/manifest.webmanifest"];
self.addEventListener("install",event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting()));});
self.addEventListener("activate",event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith("panelforge-mobile-")&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));});
self.addEventListener("fetch",event=>{
  const url=new URL(event.request.url);
  // No API/media caching, no queued commands, no automatic replay on reconnect.
  if(event.request.method!=="GET"||url.origin!==self.location.origin||url.pathname.startsWith("/api/"))return;
  if(!SHELL.includes(url.pathname+url.search))return;
  event.respondWith(fetch(event.request).then(response=>{
    if(response.ok){const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(event.request,copy));}
    return response;
  }).catch(()=>caches.match(event.request)));
});
self.addEventListener("push",event=>{
  let message={title:"Usine à vidéo",body:"Une mise à jour est disponible.",tag:"factory"};
  try{if(event.data)message={...message,...event.data.json()};}catch{}
  event.waitUntil(self.registration.showNotification(String(message.title),{
    body:String(message.body||""),tag:String(message.tag||"factory"),icon:"/icon-192.png",
    badge:"/icon-192.png",data:{url:"/"}
  }));
});
self.addEventListener("notificationclick",event=>{
  event.notification.close();
  event.waitUntil(self.clients.matchAll({type:"window",includeUncontrolled:true}).then(clients=>{
    const client=clients.find(c=>new URL(c.url).origin===self.location.origin);
    return client?client.focus():self.clients.openWindow("/");
  }));
});

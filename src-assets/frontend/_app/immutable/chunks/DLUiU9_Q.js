import"./NZTpNUN0.js";import"./69_IOA4Y.js";import{o as Fe,b as Ve,a as L,s as je,e as ue,f as I}from"./GOT-FpkN.js";import{p as Ne,g as Ue,m as k,h as r,e as n,l as me,n as Ye,k as Ge,c as v,r as m,i as K,t as Z,u as M,a as He,b as J,s as Oe,aB as P,_ as Xe}from"./C21BfNWO.js";import{i as $e}from"./DxqrWayw.js";import{e as Ke,i as Ze}from"./C_MbXwCF.js";import{s as A,b as Je,a as Q}from"./BEqU5mxu.js";import{b as Pe}from"./DqJZGdnw.js";import{b as Qe}from"./BJ8t2XEn.js";import{i as et}from"./BtQlYNB3.js";import{p as g}from"./B4gOgP0C.js";import{t as T}from"./CjU8m_MG.js";import{c as tt,n as ot,Y as rt,k as at}from"./CiYg1CIO.js";import{t as it}from"./BGPHjT8s.js";import{X as nt}from"./A8egRgcI.js";var st=I('<div class="flex items-center h-full"><div></div></div>'),ct=I(`<div class=" text-gray-500 rounded-full cursor-not-allowed"><svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="currentColor"><style>.spinner_OSmW {
								transform-origin: center;
								animation: spinner_T6mA 0.75s step-end infinite;
							}
							@keyframes spinner_T6mA {
								8.3% {
									transform: rotate(30deg);
								}
								16.6% {
									transform: rotate(60deg);
								}
								25% {
									transform: rotate(90deg);
								}
								33.3% {
									transform: rotate(120deg);
								}
								41.6% {
									transform: rotate(150deg);
								}
								50% {
									transform: rotate(180deg);
								}
								58.3% {
									transform: rotate(210deg);
								}
								66.6% {
									transform: rotate(240deg);
								}
								75% {
									transform: rotate(270deg);
								}
								83.3% {
									transform: rotate(300deg);
								}
								91.6% {
									transform: rotate(330deg);
								}
								100% {
									transform: rotate(360deg);
								}
							}</style><g class="spinner_OSmW"><rect x="11" y="1" width="2" height="5" opacity=".14"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(30 12 12)" opacity=".29"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(60 12 12)" opacity=".43"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(90 12 12)" opacity=".57"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(120 12 12)" opacity=".71"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(150 12 12)" opacity=".86"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(180 12 12)"></rect></g></svg></div>`),lt=I('<button type="button" class="p-1.5 bg-indigo-500 text-white dark:bg-indigo-500 dark:text-blue-950 rounded-full"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="size-4"><path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5"></path></svg></button>'),dt=I('<div><div class="flex items-center mr-1"><button type="button"><!></button></div> <div class="flex flex-1 self-center items-center justify-between ml-2 mx-1 overflow-hidden h-6" dir="rtl"><div class="flex items-center gap-0.5 h-6 w-full max-w-full overflow-hidden overflow-x-hidden flex-wrap"></div></div> <div class="flex"><div class="  mx-1.5 pr-1 flex justify-center items-center"><div> </div></div> <div class="flex items-center"><!></div></div></div>');function Rt(ge,l){Ne(l,!1);const ee=()=>J(tt,"$config",W),B=()=>J(ot,"$settings",W),w=()=>J(he,"$i18n",W),[W,ve]=Oe(),he=Ue("i18n");let d=g(l,"recording",12,!1),te=g(l,"transcribe",8,!0),we=g(l,"displayMedia",8,!1),pe=g(l,"echoCancellation",8,!0),ye=g(l,"noiseSuppression",8,!0),be=g(l,"autoGainControl",8,!0),ke=g(l,"className",8," p-2.5 w-full max-w-full"),oe=g(l,"confirmButtonId",8,"confirm-recording-button"),q=g(l,"onCancel",8,()=>{}),z=g(l,"onConfirm",8,e=>{}),s=k(!1),R=!1,E=k(0),F=null,D="";const xe=()=>{F=setInterval(()=>{Xe(E)},1e3)},_e=()=>{clearInterval(F),n(E,0)},Se=e=>{const t=Math.floor(e/60),o=e%60,a=o<10?`0${o}`:o;return`${t}:${a}`};let x=null;const re=async()=>{if("wakeLock"in navigator)try{x=await navigator.wakeLock.request("screen"),x.addEventListener("release",()=>{})}catch(e){}},V=async()=>{if(x){try{await x.release()}catch(e){}x=null}};let f,_=null,c,u,y=[];const Ce=-45;let p=300,i=k(Array(p).fill(0));const Me=e=>{let t=0;for(let o=0;o<e.length;o++){const a=(e[o]-128)/128;t+=a*a}return Math.sqrt(t/e.length)},Re=e=>{e=e*10;const o=Math.pow(e,1.5);return Math.min(1,Math.max(.01,o))},j=()=>{_?.close(),_=null},Ee=e=>{_=new AudioContext;const t=_.createMediaStreamSource(e),o=_.createAnalyser();o.minDecibels=Ce,t.connect(o);const a=o.frequencyBinCount,h=new Uint8Array(a),de=new Uint8Array(o.fftSize);(()=>{const fe=()=>{if(!(!d()||r(s))){if(d()&&!r(s)){o.getByteTimeDomainData(de),o.getByteFrequencyData(h);const ze=Me(de);r(i).push(Re(ze)),r(i).length>=p&&r(i).shift(),n(i,r(i))}window.requestAnimationFrame(fe)}};window.requestAnimationFrame(fe)})()},De=async(e,t="wav")=>{await P();const o=rt(e,`Recording-${at().format("YYYY-MM-DD HH-mm-ss")}.${t}`);if(te()){if(ee().audio.stt.engine==="web"||(B()?.audio?.stt?.engine??"")==="web")return;const a=await it(localStorage.token,o,B()?.audio?.stt?.language).catch(h=>(T.error(`${h}`),null));a&&z()(a)}else z()({file:o,blob:e})},Le=async()=>{n(s,!0);try{if(we()){const t=await navigator.mediaDevices.getDisplayMedia({audio:!0});f=new MediaStream;for(const o of t.getAudioTracks())f.addTrack(o);for(const o of t.getVideoTracks())o.stop()}else f=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:pe(),noiseSuppression:ye(),autoGainControl:be()}})}catch(t){T.error(w().t("Error accessing media devices.")),n(s,!1),d(!1);return}const e=["audio/webm; codecs=opus","audio/webm","audio/ogg; codecs=opus","audio/mp4","audio/wav"];u=new MediaRecorder(f,{mimeType:e.find(t=>MediaRecorder.isTypeSupported(t))}),u.onstart=async()=>{n(s,!1),xe(),(document.activeElement===document.body||!document.activeElement?.checkVisibility())&&(await P(),document.getElementById(oe())?.focus()),await re(),y=[],Ee(f)},u.ondataavailable=t=>y.push(t.data),u.onstop=async()=>{if(R){let t=y[0]?.type||u.mimeType||"audio/webm",o=t.split("/")[1].split(";")[0]||"webm";t.startsWith("audio/")||(o="webm");const a=new Blob(y,{type:t});await De(a,o),R=!1,n(s,!1)}y=[],d(!1)};try{u.start()}catch(t){T.error(w().t("Error starting recording.")),n(s,!1),d(!1);return}if(te()&&(ee().audio.stt.engine==="web"||(B()?.audio?.stt?.engine??"")==="web")&&("SpeechRecognition"in window||"webkitSpeechRecognition"in window)){D="",c=new(window.SpeechRecognition||window.webkitSpeechRecognition),c.continuous=!0,c.interimResults=!0;const t=2e3;let o;window.__callDictation&&window.__callDictation.pauseForDictation&&window.__callDictation.pauseForDictation(),c.start(),c.onresult=async a=>{clearTimeout(o);for(const h of Array.from(a.results).slice(a.resultIndex))h.isFinal&&(D=`${D}${h[0].transcript}`);await P(),document.getElementById("chat-input")?.focus(),o=setTimeout(()=>{c.stop()},t)},c.onend=function(){window.__callDictation&&window.__callDictation.resumeAfterDictation&&window.__callDictation.resumeAfterDictation(),ae(),z()({text:D}),R=!1,n(s,!1)},c.onerror=function(a){T.error(w().t("Speech recognition error: {{error}}",{error:a.error})),q()(),N()}}},N=async()=>{window.__callDictation&&window.__callDictation.resumeAfterDictation&&window.__callDictation.resumeAfterDictation(),c&&(c.onend=null),await U()},U=async()=>{d()&&u&&await u.stop(),c&&c.stop(),await V(),_e(),y=[],n(i,Array(p).fill(0)),f&&f.getTracks().forEach(t=>t.stop()),f=null,j()},ae=async()=>{n(s,!0),R=!0,d()&&u&&await u.stop(),clearInterval(F),await V(),f&&f.getTracks().forEach(t=>t.stop()),f=null,j()};let Y,G=k(),Ae=k(300),H=k();const ie=e=>{d()&&e.key==="Escape"&&r(H)?.getClientRects().length&&(e.preventDefault(),N(),q()())},ne=async()=>{d()&&document.visibilityState==="visible"&&await re()};Fe(()=>{window.addEventListener("keydown",ie),document.addEventListener("visibilitychange",ne),Y=new ResizeObserver(()=>{p=Math.floor(window.innerWidth/4),r(i).length>p?n(i,r(i).slice(r(i).length-p)):n(i,Array(p-r(i).length).fill(0).concat(r(i)))}),Y.observe(document.body)}),Ve(()=>{window.removeEventListener("keydown",ie),document.removeEventListener("visibilitychange",ne),U(),V(),j(),Y.disconnect()}),me(()=>Ye(d()),()=>{d()?Le():U()}),me(()=>r(G),()=>{n(Ae,Math.floor(r(G)/5))}),Ge(),et();var b=dt(),O=v(b),S=v(O),Te=v(S);nt(Te,{className:"size-4"}),m(S),m(O);var C=K(O,2),se=v(C);Ke(se,5,()=>(r(i),M(()=>r(i).slice().reverse())),Ze,(e,t)=>{var o=st(),a=v(o);m(o),Z(h=>{A(a,1,`w-[0.125rem] shrink-0
                    
                    ${r(s)?" bg-gray-500 dark:bg-gray-400   ":"bg-indigo-500 dark:bg-indigo-400  "} 
                    
                    inline-block h-full`),Je(a,`height: ${h??""}%;`)},[()=>(r(t),M(()=>Math.min(100,Math.max(14,r(t)*100))))]),L(e,o)}),m(se),m(C);var ce=K(C,2),X=v(ce),$=v(X),Ie=v($,!0);m($),m(X);var le=K(X,2),Be=v(le);{var We=e=>{var t=ct();L(e,t)},qe=e=>{var t=lt();Z(o=>{Q(t,"id",oe()),Q(t,"aria-label",o)},[()=>(w(),M(()=>w().t("Confirm recording")))]),ue("click",t,async()=>{await ae()}),L(e,t)};$e(Be,e=>{r(s)?e(We):e(qe,-1)})}m(le),m(ce),m(b),Qe(b,e=>n(H,e),()=>r(H)),Z((e,t)=>{A(b,1,`${r(s)?" bg-gray-100/50 dark:bg-gray-850/50":"bg-indigo-300/10 dark:bg-indigo-500/10 "} rounded-full flex justify-between ${ke()??""}`,"svelte-nkn4fu"),A(S,1,`p-1.5

            ${r(s)?" bg-gray-200 dark:bg-gray-700/50":"bg-indigo-400/20 text-indigo-600 dark:text-indigo-300 "} 


             rounded-full`),Q(S,"aria-label",e),C.dir=C.dir,A($,1,`text-sm
        
        
        ${r(s)?" text-gray-500  dark:text-gray-400  ":" text-indigo-400 "} 
       font-normal flex-1 mx-auto text-center`),je(Ie,t)},[()=>(w(),M(()=>w().t("Cancel"))),()=>(r(E),M(()=>Se(r(E))))]),ue("click",S,async()=>{N(),q()()}),Pe(b,"clientWidth",e=>n(G,e)),L(ge,b),He(),ve()}export{Rt as V};
//# sourceMappingURL=DLUiU9_Q.js.map

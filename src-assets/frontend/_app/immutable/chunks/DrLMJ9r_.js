import"./NZTpNUN0.js";import"./69_IOA4Y.js";import{p as Fe,g as Ve,m as C,o as je,l as a,k as s,x as Ne,y as ue,z as Ue,A as Ge,c as v,r as g,n as $,t as K,B as M,a as A,d as Oe,q as fe,b as He,e as J,s as Xe,F as P,f as B,aD as Ze}from"./BFUCE2bC.js";import{i as $e}from"./DYm74Khd.js";import{e as Ke,i as Je}from"./BQVpPtP4.js";import{s as D,b as Pe,a as Q}from"./BDFDMsoY.js";import{b as Qe}from"./wRtnL3KM.js";import{i as Ye}from"./yDQ1huVE.js";import{p as m}from"./FKNpzppu.js";import{t as T}from"./2JpiAfMN.js";import{p as ge,B as et,c as tt,i as ot,Z as at}from"./Bc6-PzHY.js";import{t as rt}from"./CsffpLgR.js";import{X as it}from"./BxrkqZna.js";var nt=B('<div class="flex items-center h-full"><div></div></div>'),st=B(`<div class=" text-gray-500 rounded-full cursor-not-allowed"><svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="currentColor"><style>.spinner_OSmW {
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
							}</style><g class="spinner_OSmW"><rect x="11" y="1" width="2" height="5" opacity=".14"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(30 12 12)" opacity=".29"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(60 12 12)" opacity=".43"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(90 12 12)" opacity=".57"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(120 12 12)" opacity=".71"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(150 12 12)" opacity=".86"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(180 12 12)"></rect></g></svg></div>`),ct=B('<button type="button" class="p-1.5 bg-indigo-500 text-white dark:bg-indigo-500 dark:text-blue-950 rounded-full"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="size-4"><path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5"></path></svg></button>'),lt=B('<div><div class="flex items-center mr-1"><button type="button"><!></button></div> <div class="flex flex-1 self-center items-center justify-between ml-2 mx-1 overflow-hidden h-6" dir="rtl"><div class="flex items-center gap-0.5 h-6 w-full max-w-full overflow-hidden overflow-x-hidden flex-wrap"></div></div> <div class="flex"><div class="  mx-1.5 pr-1 flex justify-center items-center"><div> </div></div> <div class="flex items-center"><!></div></div></div>');function St(me,l){Fe(l,!1);const w=()=>J(we,"$i18n",W),Y=()=>J(tt,"$config",W),I=()=>J(ot,"$settings",W),[W,ve]=Xe();ge.extend(et);const we=Ve("i18n");let d=m(l,"recording",12,!1),ee=m(l,"transcribe",8,!0),he=m(l,"displayMedia",8,!1),ye=m(l,"echoCancellation",8,!0),pe=m(l,"noiseSuppression",8,!0),be=m(l,"autoGainControl",8,!0),ke=m(l,"className",8," p-2.5 w-full max-w-full"),te=m(l,"confirmButtonId",8,"confirm-recording-button"),q=m(l,"onCancel",8,()=>{}),z=m(l,"onConfirm",8,t=>{}),n=C(!1),R=!1,E=C(0),F=null,L="";const xe=()=>{F=setInterval(()=>{Ze(E)},1e3)},_e=()=>{clearInterval(F),s(E,0)},Se=t=>{const e=Math.floor(t/60),o=t%60,r=o<10?`0${o}`:o;return`${e}:${r}`};let b=null;const oe=async()=>{if("wakeLock"in navigator)try{b=await navigator.wakeLock.request("screen"),b.addEventListener("release",()=>{})}catch(t){}},V=async()=>{if(b){try{await b.release()}catch(t){}b=null}};let u,k=null,c,f,p=[];const Ce=-45;let y=300,i=C(Array(y).fill(0));const Me=t=>{let e=0;for(let o=0;o<t.length;o++){const r=(t[o]-128)/128;e+=r*r}return Math.sqrt(e/t.length)},Re=t=>{t=t*10;const o=Math.pow(t,1.5);return Math.min(1,Math.max(.01,o))},j=()=>{k?.close(),k=null},Ee=t=>{k=new AudioContext;const e=k.createMediaStreamSource(t),o=k.createAnalyser();o.minDecibels=Ce,e.connect(o);const r=o.frequencyBinCount,h=new Uint8Array(r),le=new Uint8Array(o.fftSize);(()=>{const de=()=>{if(!(!d()||a(n))){if(d()&&!a(n)){o.getByteTimeDomainData(le),o.getByteFrequencyData(h);const ze=Me(le);a(i).push(Re(ze)),a(i).length>=y&&a(i).shift(),s(i,a(i))}window.requestAnimationFrame(de)}};window.requestAnimationFrame(de)})()},Le=async(t,e="wav")=>{await P();const o=at(t,`Recording-${ge().locale(w().language).format("L LT")}.${e}`);if(ee()){if(Y().audio.stt.engine==="web"||(I()?.audio?.stt?.engine??"")==="web")return;const r=await rt(localStorage.token,o,I()?.audio?.stt?.language).catch(h=>(T.error(`${h}`),null));r&&z()(r)}else z()({file:o,blob:t})},Ae=async()=>{s(n,!0);try{if(he()){const e=await navigator.mediaDevices.getDisplayMedia({audio:!0});u=new MediaStream;for(const o of e.getAudioTracks())u.addTrack(o);for(const o of e.getVideoTracks())o.stop()}else u=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:ye(),noiseSuppression:pe(),autoGainControl:be()}})}catch(e){T.error(w().t("Error accessing media devices.")),s(n,!1),d(!1);return}const t=["audio/webm; codecs=opus","audio/webm","audio/ogg; codecs=opus","audio/mp4","audio/wav"];f=new MediaRecorder(u,{mimeType:t.find(e=>MediaRecorder.isTypeSupported(e))}),f.onstart=async()=>{s(n,!1),xe(),(document.activeElement===document.body||!document.activeElement?.checkVisibility())&&(await P(),document.getElementById(te())?.focus()),await oe(),p=[],Ee(u)},f.ondataavailable=e=>p.push(e.data),f.onstop=async()=>{if(R){let e=p[0]?.type||f.mimeType||"audio/webm",o=e.split("/")[1].split(";")[0]||"webm";e.startsWith("audio/")||(o="webm");const r=new Blob(p,{type:e});await Le(r,o),R=!1,s(n,!1)}p=[],d(!1)};try{f.start()}catch(e){T.error(w().t("Error starting recording.")),s(n,!1),d(!1);return}if(ee()&&(Y().audio.stt.engine==="web"||(I()?.audio?.stt?.engine??"")==="web")&&("SpeechRecognition"in window||"webkitSpeechRecognition"in window)){L="",c=new(window.SpeechRecognition||window.webkitSpeechRecognition),c.continuous=!0,c.interimResults=!0;const e=2e3;let o;c.start(),c.onresult=async r=>{clearTimeout(o);for(const h of Array.from(r.results).slice(r.resultIndex))h.isFinal&&(L=`${L}${h[0].transcript}`);await P(),document.getElementById("chat-input")?.focus(),o=setTimeout(()=>{c.stop()},e)},c.onend=function(){ae(),z()({text:L}),R=!1,s(n,!1)},c.onerror=function(r){T.error(w().t("Speech recognition error: {{error}}",{error:r.error})),q()(),N()}}},N=async()=>{c&&(c.onend=null),await U()},U=async()=>{d()&&f&&await f.stop(),c&&c.stop(),await V(),_e(),p=[],s(i,Array(y).fill(0)),u&&u.getTracks().forEach(e=>e.stop()),u=null,j()},ae=async()=>{s(n,!0),R=!0,d()&&f&&await f.stop(),clearInterval(F),await V(),u&&u.getTracks().forEach(e=>e.stop()),u=null,j()};let G,O=C(),De=C(300);const re=t=>{d()&&t.key==="Escape"&&(t.preventDefault(),N(),q()())},ie=async()=>{d()&&document.visibilityState==="visible"&&await oe()};je(()=>{window.addEventListener("keydown",re),document.addEventListener("visibilitychange",ie),G=new ResizeObserver(()=>{y=Math.floor(window.innerWidth/4),a(i).length>y?s(i,a(i).slice(a(i).length-y)):s(i,Array(y-a(i).length).fill(0).concat(a(i)))}),G.observe(document.body)}),Ne(()=>{window.removeEventListener("keydown",re),document.removeEventListener("visibilitychange",ie),U(),V(),j(),G.disconnect()}),ue(()=>Ue(d()),()=>{d()?Ae():U()}),ue(()=>a(O),()=>{s(De,Math.floor(a(O)/5))}),Ge(),Ye();var x=lt(),H=v(x),_=v(H),Te=v(_);it(Te,{className:"size-4"}),g(_),g(H);var S=$(H,2),ne=v(S);Ke(ne,5,()=>(a(i),M(()=>a(i).slice().reverse())),Je,(t,e)=>{var o=nt(),r=v(o);g(o),K(h=>{D(r,1,`w-[0.125rem] shrink-0
                    
                    ${a(n)?" bg-gray-500 dark:bg-gray-400   ":"bg-indigo-500 dark:bg-indigo-400  "} 
                    
                    inline-block h-full`),Pe(r,`height: ${h??""}%;`)},[()=>(a(e),M(()=>Math.min(100,Math.max(14,a(e)*100))))]),A(t,o)}),g(ne),g(S);var se=$(S,2),X=v(se),Z=v(X),Be=v(Z,!0);g(Z),g(X);var ce=$(X,2),Ie=v(ce);{var We=t=>{var e=st();A(t,e)},qe=t=>{var e=ct();K(o=>{Q(e,"id",te()),Q(e,"aria-label",o)},[()=>(w(),M(()=>w().t("Confirm recording")))]),fe("click",e,async()=>{await ae()}),A(t,e)};$e(Ie,t=>{a(n)?t(We):t(qe,-1)})}g(ce),g(se),g(x),K((t,e)=>{D(x,1,`${a(n)?" bg-gray-100/50 dark:bg-gray-850/50":"bg-indigo-300/10 dark:bg-indigo-500/10 "} rounded-full flex justify-between ${ke()??""}`,"svelte-nkn4fu"),D(_,1,`p-1.5

            ${a(n)?" bg-gray-200 dark:bg-gray-700/50":"bg-indigo-400/20 text-indigo-600 dark:text-indigo-300 "} 


             rounded-full`),Q(_,"aria-label",t),S.dir=S.dir,D(Z,1,`text-sm
        
        
        ${a(n)?" text-gray-500  dark:text-gray-400  ":" text-indigo-400 "} 
       font-normal flex-1 mx-auto text-center`),Oe(Be,e)},[()=>(w(),M(()=>w().t("Cancel"))),()=>(a(E),M(()=>Se(a(E))))]),fe("click",_,async()=>{N(),q()()}),Qe(x,"clientWidth",t=>s(O,t)),A(me,x),He(),ve()}export{St as V};
//# sourceMappingURL=DrLMJ9r_.js.map

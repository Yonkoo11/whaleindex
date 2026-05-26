// Records a scripted screencast of the live WhaleIndex site, paced to the VO timeline.
// A read-only EIP-1193 provider is injected so the buy panel shows the real on-chain
// holder + live balances; it forwards every call to the public Arc RPC and CANNOT sign,
// so no transaction is ever sent (we never click submit). No data is fabricated.
import { readFileSync } from "node:fs";
import puppeteer from "puppeteer-core";
import { PuppeteerScreenRecorder } from "puppeteer-screen-recorder";

const CHROME = "/Users/yonko/.cache/puppeteer/chrome/mac_arm-146.0.7680.153/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";
const SITE = "http://localhost:8099/index.html";
const RPC = "https://rpc.testnet.arc.network";
const CHAIN_HEX = "0x4CEDD2"; // 5042002
const HOLDER = "0xf9946775891a24462cD4ec885d0D4E2675C84355"; // real holder of 1 WHALE

const tl = JSON.parse(readFileSync(new URL("./out/timeline.json", import.meta.url)));
const GAP = tl.gap;
const sec = (name) => tl.segments.find((s) => s.section === name);
const budget = (name) => sec(name).dur + GAP; // seconds available for this section
const sleep = (s) => new Promise((r) => setTimeout(r, Math.round(s * 1000)));

// Parse captions.srt into cues (seconds relative to VO start) for the in-page overlay.
function parseCues() {
  const srt = readFileSync(new URL("./out/captions.srt", import.meta.url), "utf8");
  const toSec = (t) => {
    const [hms, ms] = t.split(",");
    const [h, m, s] = hms.split(":");
    return +h * 3600 + +m * 60 + +s + +ms / 1000;
  };
  const cues = [];
  for (const b of srt.trim().split(/\n\s*\n/)) {
    const lines = b.split("\n");
    const tline = lines.find((l) => l.includes("-->"));
    if (!tline) continue;
    const [s, e] = tline.split("-->").map((x) => x.trim());
    const text = lines.slice(lines.indexOf(tline) + 1).join(" ").trim();
    if (text) cues.push({ start: toSec(s), end: toSec(e), text });
  }
  return cues;
}
const CUES = parseCues();

const injected = `
window.ethereum = (function(){
  const RPC=${JSON.stringify(RPC)}, CHAIN=${JSON.stringify(CHAIN_HEX)}, ACCT=${JSON.stringify(HOLDER)};
  let id=0; const listeners={};
  async function fwd(method, params){
    const res=await fetch(RPC,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({jsonrpc:'2.0',id:++id,method,params:params||[]})});
    const j=await res.json(); if(j.error) throw new Error(j.error.message); return j.result;
  }
  return {
    isMetaMask:true,
    request: async ({method, params})=>{
      switch(method){
        case 'eth_requestAccounts':
        case 'eth_accounts': return [ACCT];
        case 'eth_chainId': return CHAIN;
        case 'net_version': return String(parseInt(CHAIN,16));
        case 'wallet_switchEthereumChain':
        case 'wallet_addEthereumChain': return null;
        default: return fwd(method, params);
      }
    },
    on:(e,cb)=>{(listeners[e]=listeners[e]||[]).push(cb);},
    removeListener:()=>{}, removeAllListeners:()=>{},
  };
})();
`;

// Smoothly scroll the document to bring a selector to a target viewport position.
async function glide(page, selector, durS, align = 0.28) {
  await page.evaluate(
    async (sel, dur, al) => {
      const el = document.querySelector(sel);
      if (!el) return;
      const startY = window.scrollY;
      const rect = el.getBoundingClientRect();
      const targetY = startY + rect.top - window.innerHeight * al;
      const dist = targetY - startY;
      const t0 = performance.now();
      const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
      await new Promise((done) => {
        function step(now) {
          const p = Math.min(1, (now - t0) / (dur * 1000));
          window.scrollTo(0, startY + dist * ease(p));
          if (p < 1) requestAnimationFrame(step); else done();
        }
        requestAnimationFrame(step);
      });
    },
    selector, durS, align
  );
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    defaultViewport: { width: 1280, height: 800, deviceScaleFactor: 2 },
    args: ["--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--force-color-profile=srgb"],
  });
  const page = await browser.newPage();
  await page.evaluateOnNewDocument(injected);
  await page.goto(SITE, { waitUntil: "networkidle2", timeout: 60000 });
  await sleep(3.5); // let live RPC reads + decision-latest.json populate

  const recorder = new PuppeteerScreenRecorder(page, {
    fps: 30,
    videoFrame: { width: 1280, height: 800 },
    aspectRatio: "16:9",
  });
  await recorder.start("out/raw.mp4");

  // Inject a synced caption bar that the screencast captures (no libass needed).
  await page.evaluate((cues) => {
    const el = document.createElement("div");
    el.id = "vo-cap";
    Object.assign(el.style, {
      position: "fixed", left: "50%", bottom: "46px", transform: "translateX(-50%)",
      maxWidth: "880px", padding: "12px 22px", borderRadius: "12px",
      background: "rgba(6,10,12,0.82)", color: "#fff",
      fontFamily: "'DM Sans',-apple-system,system-ui,sans-serif",
      fontSize: "23px", fontWeight: "600", lineHeight: "1.4", textAlign: "center",
      letterSpacing: "-0.01em", zIndex: "2147483647",
      boxShadow: "0 8px 30px rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.10)",
      backdropFilter: "blur(6px)", opacity: "0", transition: "opacity 160ms ease",
      pointerEvents: "none", whiteSpace: "normal",
    });
    document.body.appendChild(el);
    const t0 = performance.now();
    (function tick() {
      const t = (performance.now() - t0) / 1000;
      const c = cues.find((q) => t >= q.start && t < q.end);
      if (c) { if (el.textContent !== c.text) el.textContent = c.text; el.style.opacity = "1"; }
      else el.style.opacity = "0";
      requestAnimationFrame(tick);
    })();
  }, CUES);

  const log = (m) => console.log(`  ${m}`);

  // 1) HOOK — hold on the hero thesis line
  log(`hook (${budget("hook").toFixed(1)}s)`);
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(budget("hook") - 2.0);
  await glide(page, "#pipelineNodes", 2.0, 0.55); // begin drifting toward the pipeline

  // 2) WHAT — settle on the four-agent pipeline, walk the nodes
  log(`what (${budget("what").toFixed(1)}s)`);
  await glide(page, "#pipelineNodes", 2.0, 0.18);
  const nodes = ["scorer", "allocator", "risk", "coordinator"];
  const per = (budget("what") - 2.0) / nodes.length;
  for (const n of nodes) {
    await page.hover(`[data-node="${n}"]`).catch(() => {});
    await sleep(per);
  }

  // 3) DIFFERENTIATOR — open the Risk agent to show the veto reasoning
  log(`differentiator (${budget("differentiator").toFixed(1)}s)`);
  await page.hover('[data-node="risk"]').catch(() => {});
  await sleep(1.0);
  await page.click('[data-node="risk"]').catch(() => {});
  await sleep(budget("differentiator") - 2.5); // hold on the veto panel
  await page.keyboard.press("Escape").catch(() => {});
  await sleep(1.0);

  // 4) VERIFY — expand the full record / ledger and pan through it
  log(`verify (${budget("verify").toFixed(1)}s)`);
  await glide(page, "#recordCell", 1.6, 0.22); // hash + audit trail
  await sleep(1.4);
  await glide(page, "#ledger", 1.6, 0.12);
  await page.click("#ledgerToggle").catch(() => {});
  await sleep(1.0);
  await glide(page, "#ledgerVetoBody", Math.max(1.5, budget("verify") - 5.6), 0.2);

  // 5) BUY — open the panel, connect the read-only wallet, type a real amount
  log(`buy (${budget("buy").toFixed(1)}s)`);
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(0.6);
  await page.click("#connectBtn").catch(() => {});
  await sleep(1.2);
  await page.click("#doConnect").catch(() => {}); // runs the page's connectWallet listener
  await sleep(2.5); // form reveals with real balances from the live RPC
  await page.click("#buyAmt").catch(() => {});
  await page.type("#buyAmt", "25.00", { delay: 140 });
  await sleep(budget("buy") - 6.0); // hold on estimated shares
  await page.keyboard.press("Escape").catch(() => {});
  await sleep(0.4);

  // 6) CLOSE — verified contracts + attestation, land back on the thesis
  log(`close (${budget("close").toFixed(1)}s)`);
  await glide(page, "#contractsCell", 2.0, 0.16);
  await sleep(Math.max(1.5, (budget("close") - 6.5) / 2));
  await glide(page, "#attestCell", 1.8, 0.16);
  await sleep(Math.max(1.5, (budget("close") - 6.5) / 2));
  await glide(page, "#pipeline", 2.0, 0.0);
  await sleep(1.0);

  await recorder.stop();
  await browser.close();
  console.log("wrote out/raw.mp4");
})().catch((e) => { console.error(e); process.exit(1); });

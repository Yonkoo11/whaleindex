// Generates per-segment voiceover clips + a synced caption timeline.
// Uses ElevenLabs with-timestamps so durations come from the API (no ffprobe).
// The API key is read from process.env at runtime and never logged.
import { readFileSync, writeFileSync } from "node:fs";

const KEY = process.env.ELEVENLABS_API_KEY;
if (!KEY) { console.error("ELEVENLABS_API_KEY not in env"); process.exit(1); }

const VOICE = "pNInz6obpgDQGcFmaJgB"; // Adam — calm, credible product narration
const MODEL = "eleven_multilingual_v2";
const GAP = 0.4; // seconds of silence inserted between segments

const segs = JSON.parse(readFileSync(new URL("./segments.json", import.meta.url)));

// Split a caption into readable chunks (<= ~70 chars), preserving sentence flow.
function chunkCaption(text) {
  const sentences = text.split(/(?<=[.?!;:])\s+/).filter(Boolean);
  const chunks = [];
  for (const s of sentences) {
    if (s.length <= 72) { chunks.push(s); continue; }
    let buf = "";
    for (const part of s.split(/(?<=,)\s+/)) {
      if ((buf + " " + part).trim().length > 72 && buf) { chunks.push(buf.trim()); buf = part; }
      else buf = (buf + " " + part).trim();
    }
    if (buf) chunks.push(buf.trim());
  }
  return chunks;
}

function srtTime(t) {
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = Math.floor(t % 60);
  const ms = Math.round((t - Math.floor(t)) * 1000);
  const p = (n, l = 2) => String(n).padStart(l, "0");
  return `${p(h)}:${p(m)}:${p(s)},${p(ms, 3)}`;
}

const timeline = [];
const srt = [];
let offset = 0;
let srtIdx = 1;

for (const seg of segs) {
  process.stdout.write(`segment ${seg.id} (${seg.section}) ... `);
  const res = await fetch(
    `https://api.elevenlabs.io/v1/text-to-speech/${VOICE}/with-timestamps`,
    {
      method: "POST",
      headers: { "xi-api-key": KEY, "Content-Type": "application/json" },
      body: JSON.stringify({
        text: seg.tts,
        model_id: MODEL,
        voice_settings: { stability: 0.5, similarity_boost: 0.75, style: 0.0, use_speaker_boost: true },
      }),
    }
  );
  if (!res.ok) {
    console.error(`\nElevenLabs error ${res.status}: ${await res.text()}`);
    process.exit(1);
  }
  const data = await res.json();
  writeFileSync(`out/seg-${seg.id}.mp3`, Buffer.from(data.audio_base64, "base64"));
  const ends = data.alignment?.character_end_times_seconds || [];
  const dur = ends.length ? ends[ends.length - 1] : 0;
  console.log(`${dur.toFixed(2)}s`);

  const chunks = chunkCaption(seg.caption);
  const totalChars = chunks.reduce((a, c) => a + c.length, 0) || 1;
  let t = offset;
  for (const c of chunks) {
    const cdur = (c.length / totalChars) * dur;
    srt.push(`${srtIdx++}\n${srtTime(t)} --> ${srtTime(t + cdur)}\n${c}\n`);
    t += cdur;
  }

  timeline.push({ id: seg.id, section: seg.section, start: offset, dur });
  offset += dur + GAP;
}

writeFileSync("out/timeline.json", JSON.stringify({ gap: GAP, total: offset - GAP, segments: timeline }, null, 2));
writeFileSync("out/captions.srt", srt.join("\n"));
const total = offset - GAP;
console.log(`\nTotal VO: ${total.toFixed(1)}s (${(total / 60).toFixed(2)} min)`);
console.log("Wrote seg mp3s, timeline.json, captions.srt");

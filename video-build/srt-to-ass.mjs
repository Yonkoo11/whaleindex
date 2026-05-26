// Convert captions.srt -> styled captions.ass (avoids ffmpeg force_style escaping).
import { readFileSync, writeFileSync } from "node:fs";

const srt = readFileSync("out/captions.srt", "utf8");

// SRT "HH:MM:SS,mmm" -> ASS "H:MM:SS.cc"
const toAss = (t) => {
  const [hms, ms] = t.split(",");
  const [h, m, s] = hms.split(":");
  const cc = String(Math.round(parseInt(ms, 10) / 10)).padStart(2, "0");
  return `${parseInt(h, 10)}:${m}:${s}.${cc}`;
};

const dialogue = [];
for (const block of srt.trim().split(/\n\s*\n/)) {
  const lines = block.split("\n");
  const timing = lines.find((l) => l.includes("-->"));
  if (!timing) continue;
  const [start, end] = timing.split("-->").map((x) => x.trim());
  const text = lines.slice(lines.indexOf(timing) + 1).join("\\N").trim();
  if (!text) continue;
  dialogue.push(`Dialogue: 0,${toAss(start)},${toAss(end)},Cap,,0,0,0,,${text}`);
}

const ass = `[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 800
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Helvetica Neue,25,&H00FFFFFF,&H00FFFFFF,&H50000000,&H96000000,1,0,0,0,100,100,0,0,3,6,0,2,120,120,46,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
${dialogue.join("\n")}
`;

writeFileSync("out/captions.ass", ass);
console.log(`wrote out/captions.ass (${dialogue.length} cues)`);

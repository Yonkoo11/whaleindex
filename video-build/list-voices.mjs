// Print voice name + id for voices matching a query. Key read from env, never logged.
const KEY = process.env.ELEVENLABS_API_KEY;
const q = (process.argv[2] || "").toLowerCase();
const res = await fetch("https://api.elevenlabs.io/v1/voices", { headers: { "xi-api-key": KEY } });
const { voices } = await res.json();
for (const v of voices) {
  if (!q || v.name.toLowerCase().includes(q)) console.log(`${v.name}\t${v.voice_id}\t${v.labels?.accent || ""} ${v.labels?.description || ""}`);
}

import { Stitch, StitchToolClient } from "@google/stitch-sdk";

const client = new StitchToolClient({
  apiKey: process.env.STITCH_API_KEY || "installation-check",
});
const sdk = new Stitch(client);

console.log(JSON.stringify({
  installed: Boolean(sdk),
  authenticated: Boolean(
    process.env.STITCH_API_KEY || process.env.STITCH_ACCESS_TOKEN
  ),
  node: process.version,
}, null, 2));
await client.close();

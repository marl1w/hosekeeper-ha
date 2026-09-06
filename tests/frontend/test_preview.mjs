// The preview page, booted the way a browser boots it.
//
// Every earlier check verified the parts: the modules parse, the views render, the server
// answers 200. None of them ran the page, so a stale line in the page's own script — one
// that looked up a lawn by a key the sample no longer used — left the panel blank while
// every check passed. This starts the real server, takes its real page, and executes that
// page's own module script against the real endpoints.
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { installDom, byClass } from "./dom-shim.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const frontend = pathToFileURL(join(root, "custom_components", "hosekeeper", "frontend") + "/").href;
const port = 8200 + Math.floor(Math.random() * 500);

installDom();

const server = spawn(join(root, ".venv", "bin", "python"), ["scripts/preview.py", "--port", String(port), "--lang", "en"], {
  cwd: root,
  stdio: ["ignore", "pipe", "pipe"],
});
let serverErrors = "";
server.stderr.on("data", (chunk) => {
  serverErrors += chunk.toString();
});

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function ready() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/api/snapshot`);
      if (response.ok) return true;
    } catch {
      /* not up yet */
    }
    await wait(250);
  }
  return false;
}

let failed = 0;
const fail = (message) => {
  console.error(`  ${message}`);
  failed = 1;
};

try {
  if (!(await ready())) {
    fail(`the preview server never came up${serverErrors ? `: ${serverErrors.split("\n")[0]}` : ""}`);
  } else {
    const page = await (await fetch(`http://127.0.0.1:${port}/`)).text();
    const script = page.slice(page.indexOf('<script type="module">') + 22, page.indexOf("</script>"));
    if (!script.includes("hosekeeper-panel")) fail("the page does not load the panel");

    // The page fetches relative URLs and imports "/frontend/...": give it an absolute
    // origin and a file URL, and otherwise run its own code, unaltered.
    const runnable = script
      .replaceAll('fetch("/api/', `fetch("http://127.0.0.1:${port}/api/`)
      .replaceAll('import("/frontend/', `import("${frontend}`);
    const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor;
    try {
      await new AsyncFunction(runnable)();
    } catch (error) {
      fail(`the page threw while starting: ${error.message}`);
    }

    const panel = document.body.children.find((node) => node.localName === "hosekeeper-panel");
    if (!panel) {
      fail("the page never added the panel to the document");
    } else {
      for (let attempt = 0; attempt < 20; attempt += 1) await wait(20);
      const content = panel.shadowRoot?.find(byClass("content"));
      const text = content?.textContent || "";
      const snapshot = await (await fetch(`http://127.0.0.1:${port}/api/snapshot`)).json();
      const names = Object.values(snapshot).map((lawn) => lawn.field.name);
      if (!text.trim()) {
        fail("the panel rendered a blank page");
      }
      for (const name of names) {
        if (!text.includes(name)) fail(`${name} is missing from the page`);
      }
      if (!panel.shadowRoot.find(byClass("glance__row"))) fail("no lawns at a glance");
      if (!panel.shadowRoot.find(byClass("segmented"))) fail("no view switch");
    }
  }
} finally {
  server.kill("SIGTERM");
}

if (!failed) console.log("  the preview page boots and shows every lawn");
process.exit(failed);

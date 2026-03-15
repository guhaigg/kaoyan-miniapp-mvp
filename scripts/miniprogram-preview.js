const fs = require("fs");
const path = require("path");
const ci = require("miniprogram-ci");

const repoRoot = path.resolve(__dirname, "..");
const miniappRoot = path.join(repoRoot, "miniapp");
const projectConfigPath = path.join(miniappRoot, "project.config.json");

function parseArgs(argv) {
  const parsed = {};

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      continue;
    }

    const raw = token.slice(2);
    const eqIndex = raw.indexOf("=");
    if (eqIndex >= 0) {
      const key = raw.slice(0, eqIndex);
      const value = raw.slice(eqIndex + 1);
      parsed[key] = value;
      continue;
    }

    const next = argv[i + 1];
    if (next && !next.startsWith("--")) {
      parsed[raw] = next;
      i += 1;
      continue;
    }

    parsed[raw] = true;
  }

  return parsed;
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function resolveFromRepo(filePath) {
  return path.isAbsolute(filePath) ? filePath : path.resolve(repoRoot, filePath);
}

function toNumber(value, fallback) {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }

  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    throw new Error(`invalid numeric value: ${value}`);
  }
  return parsed;
}

function buildVersion() {
  const now = new Date();
  const parts = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
    String(now.getHours()).padStart(2, "0"),
    String(now.getMinutes()).padStart(2, "0"),
    String(now.getSeconds()).padStart(2, "0"),
  ];

  return `preview-${parts.join("")}`;
}

function printHelp() {
  console.log(`Usage:
  npm run smoke:miniapp:preview -- --privateKeyPath .secrets/miniprogram-ci.key

Options:
  --privateKeyPath    Required. WeChat code upload private key path.
  --appid             Optional. Overrides miniapp/project.config.json appid.
  --pagePath          Optional. Launch page path, e.g. pages/announcements/index
  --searchQuery       Optional. Query string for launch page.
  --scene             Optional. Launch scene number.
  --robot             Optional. CI robot number, default 1.
  --threads           Optional. Local compile threads, default 4.
  --version           Optional. Preview version label.
  --desc              Optional. Preview description.
  --qrcodeOutput      Optional. QR code output path, default artifacts/miniprogram-preview.jpg

Environment variable fallbacks:
  MINIPROGRAM_PRIVATE_KEY_PATH
  MINIPROGRAM_APPID
  MINIPROGRAM_PREVIEW_PAGE_PATH
  MINIPROGRAM_PREVIEW_SEARCH_QUERY
  MINIPROGRAM_PREVIEW_SCENE
  MINIPROGRAM_PREVIEW_ROBOT
  MINIPROGRAM_PREVIEW_THREADS
  MINIPROGRAM_PREVIEW_VERSION
  MINIPROGRAM_PREVIEW_DESC
  MINIPROGRAM_PREVIEW_QRCODE_PATH
`);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || args.h) {
    printHelp();
    return;
  }

  if (!fs.existsSync(projectConfigPath)) {
    throw new Error(`missing project config: ${projectConfigPath}`);
  }

  const projectConfig = readJson(projectConfigPath);
  const appid = args.appid || process.env.MINIPROGRAM_APPID || projectConfig.appid;
  const privateKeyInput =
    args.privateKeyPath || process.env.MINIPROGRAM_PRIVATE_KEY_PATH || "";

  if (!privateKeyInput) {
    throw new Error(
      "missing private key path, pass --privateKeyPath or set MINIPROGRAM_PRIVATE_KEY_PATH"
    );
  }

  const privateKeyPath = resolveFromRepo(privateKeyInput);
  if (!fs.existsSync(privateKeyPath)) {
    throw new Error(`private key not found: ${privateKeyPath}`);
  }

  const qrcodeOutputDest = resolveFromRepo(
    args.qrcodeOutput ||
      process.env.MINIPROGRAM_PREVIEW_QRCODE_PATH ||
      "artifacts/miniprogram-preview.jpg"
  );
  fs.mkdirSync(path.dirname(qrcodeOutputDest), { recursive: true });

  const pagePath = args.pagePath || process.env.MINIPROGRAM_PREVIEW_PAGE_PATH;
  const searchQuery = args.searchQuery || process.env.MINIPROGRAM_PREVIEW_SEARCH_QUERY;
  const scene = toNumber(args.scene || process.env.MINIPROGRAM_PREVIEW_SCENE, undefined);
  const robot = toNumber(args.robot || process.env.MINIPROGRAM_PREVIEW_ROBOT, 1);
  const threads = toNumber(args.threads || process.env.MINIPROGRAM_PREVIEW_THREADS, 4);
  const version = args.version || process.env.MINIPROGRAM_PREVIEW_VERSION || buildVersion();
  const desc =
    args.desc ||
    process.env.MINIPROGRAM_PREVIEW_DESC ||
    "Ubuntu smoke preview via miniprogram-ci";

  const compileSetting = {
    es6: Boolean(projectConfig.setting?.es6),
    es7: Boolean(projectConfig.setting?.enhance),
    minify: Boolean(projectConfig.setting?.minified),
    minifyJS: Boolean(projectConfig.setting?.minified),
    minifyWXML: Boolean(projectConfig.setting?.minified),
    minifyWXSS: Boolean(projectConfig.setting?.minified),
    autoPrefixWXSS: Boolean(projectConfig.setting?.postcss),
  };

  const project = new ci.Project({
    appid,
    type: "miniProgram",
    projectPath: miniappRoot,
    privateKeyPath,
  });

  console.log("Starting miniapp preview...");
  console.log(`- appid: ${appid}`);
  console.log(`- projectPath: ${miniappRoot}`);
  console.log(`- qrcodeOutput: ${qrcodeOutputDest}`);
  if (pagePath) {
    console.log(`- pagePath: ${pagePath}`);
  }
  if (searchQuery) {
    console.log(`- searchQuery: ${searchQuery}`);
  }
  if (scene !== undefined) {
    console.log(`- scene: ${scene}`);
  }

  await ci.preview({
    project,
    version,
    desc,
    robot,
    threads,
    setting: compileSetting,
    qrcodeFormat: "image",
    qrcodeOutputDest,
    pagePath,
    searchQuery,
    scene,
    onProgressUpdate(update) {
      if (typeof update === "string") {
        console.log(`[ci] ${update}`);
        return;
      }

      const status = [];
      if (update.message) {
        status.push(update.message);
      }
      if (update.status) {
        status.push(String(update.status));
      }
      if (typeof update.progress === "number") {
        status.push(`${update.progress}%`);
      }
      if (status.length) {
        console.log(`[ci] ${status.join(" | ")}`);
      }
    },
  });

  console.log("");
  console.log("Preview QR generated successfully.");
  console.log(`- file: ${qrcodeOutputDest}`);
  console.log("- next: scan the QR code in WeChat and walk through home -> list -> detail.");
}

main().catch((error) => {
  console.error("Miniapp preview failed.");
  console.error(error && error.message ? error.message : error);
  process.exitCode = 1;
});

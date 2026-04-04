const baileys = require("/app/node_modules/@whiskeysockets/baileys");
const pino = require("/app/node_modules/pino");

const { useMultiFileAuthState, makeWASocket, fetchLatestBaileysVersion, makeCacheableSignalKeyStore } = baileys;

async function main() {
  const logger = pino({ level: "silent" });
  const authDir = "/home/openclaw/.openclaw/credentials/whatsapp/default";

  const { state } = await useMultiFileAuthState(authDir);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    version,
    logger,
    printQRInTerminal: false,
    browser: ["openclaw", "cli", "1.0"],
    syncFullHistory: false,
    markOnlineOnConnect: false,
  });

  // Wait for connection
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error("Connection timeout")), 30000);
    sock.ev.on("connection.update", (update) => {
      if (update.connection === "open") {
        clearTimeout(timeout);
        resolve();
      }
      if (update.connection === "close") {
        clearTimeout(timeout);
        reject(new Error("Connection closed"));
      }
    });
  });

  // Fetch all groups
  const groups = await sock.groupFetchAllParticipating();
  const result = {};
  for (const [jid, meta] of Object.entries(groups)) {
    result[jid] = {
      subject: meta.subject,
      size: meta.size || (meta.participants ? meta.participants.length : 0),
      creation: meta.creation,
      desc: meta.desc ? meta.desc.substring(0, 100) : null,
    };
  }

  console.log(JSON.stringify(result, null, 2));

  // Clean disconnect without logging out
  sock.end(undefined);
  setTimeout(() => process.exit(0), 1000);
}

main().catch(err => {
  console.error("ERROR:", err.message);
  process.exit(1);
});

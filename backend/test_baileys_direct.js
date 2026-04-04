const authDir = "/home/openclaw/.openclaw/credentials/whatsapp/default/";
const { useMultiFileAuthState, makeWASocket, makeCacheableSignalKeyStore, fetchLatestBaileysVersion } = require("/app/node_modules/@whiskeysockets/baileys");
const pino = require("/app/node_modules/pino");
const logger = pino({ level: "warn" });

(async () => {
  try {
    const { state, saveCreds } = await useMultiFileAuthState(authDir);
    const { version } = await fetchLatestBaileysVersion();
    console.log("ver:", JSON.stringify(version));
    console.log("reg:", state.creds && state.creds.registered);

    const sock = makeWASocket({
      auth: { creds: state.creds, keys: makeCacheableSignalKeyStore(state.keys, logger) },
      version,
      logger,
      printQRInTerminal: false,
      browser: ["test", "cli", "1.0"],
      syncFullHistory: false,
      shouldSyncHistoryMessage: function() { return false; },
      markOnlineOnConnect: true
    });

    sock.ev.on("connection.update", function(update) {
      console.log("CONN:" + JSON.stringify(update));
      if (update.connection === "close") {
        console.log("CLOSED");
        process.exit(1);
      }
      if (update.connection === "open") {
        console.log("OPEN - send a WhatsApp message now!");
      }
    });

    sock.ev.on("messages.upsert", function(upsert) {
      console.log("MSG_UPSERT type=" + upsert.type + " count=" + (upsert.messages ? upsert.messages.length : 0));
      var msgs = upsert.messages || [];
      for (var i = 0; i < msgs.length; i++) {
        var m = msgs[i];
        var jid = m.key && m.key.remoteJid ? m.key.remoteJid : "?";
        var push = m.pushName || "?";
        var fromMe = m.key && m.key.fromMe;
        console.log("  jid=" + jid + " push=" + push + " fromMe=" + fromMe);
      }
    });

    sock.ev.on("creds.update", saveCreds);

    setTimeout(function() {
      console.log("TIMEOUT_120s");
      process.exit(0);
    }, 120000);
  } catch (err) {
    console.error("ERROR:", err);
    process.exit(1);
  }
})();

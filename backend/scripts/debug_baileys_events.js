(async () => {
  const { makeWASocket, useMultiFileAuthState, fetchLatestBaileysVersion, makeCacheableSignalKeyStore } = await import("@whiskeysockets/baileys");
  const authDir = "/home/openclaw/.openclaw/credentials/whatsapp/default";
  const { state, saveCreds } = await useMultiFileAuthState(authDir);
  const { version } = await fetchLatestBaileysVersion();
  
  console.log("Creating test socket...");
  console.log("Creds registered:", state.creds.registered);
  console.log("Creds me:", JSON.stringify(state.creds.me));

  const noop = { level:"silent", trace(){}, debug(){}, info(){}, warn(){}, error(){}, fatal(){}, child(){ return this; } };
  const sock = makeWASocket({
    auth: { creds: state.creds, keys: makeCacheableSignalKeyStore(state.keys, noop) },
    version,
    printQRInTerminal: false,
    browser: ["test", "debug", "1.0"],
    syncFullHistory: false,
    shouldSyncHistoryMessage: () => true,
    markOnlineOnConnect: false,
  });

  const events = ["connection.update","creds.update","messages.upsert","messages.update","messages.delete","message-receipt.update","groups.upsert","groups.update","presence.update","chats.upsert","chats.update","chats.delete","contacts.upsert","contacts.update","messaging-history.set"];
  
  for (const ev of events) {
    sock.ev.on(ev, (data) => {
      let summary;
      if (ev === "messages.upsert") {
        summary = JSON.stringify(data, null, 2).substring(0, 500);
      } else {
        summary = JSON.stringify(data).substring(0, 150);
      }
      console.log("[EVENT " + new Date().toISOString() + "] " + ev + ": " + summary);
    });
  }
  
  sock.ev.on("creds.update", saveCreds);
  
  console.log("Waiting 60 seconds for events... Send a message NOW!");
  setTimeout(() => {
    console.log("Test complete. Closing.");
    try { sock.end(undefined); } catch(e) {}
    process.exit(0);
  }, 60000);
})().catch(err => { console.error("Error:", err); process.exit(1); });

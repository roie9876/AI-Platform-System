const baileys = await import('/app/node_modules/@whiskeysockets/baileys/lib/index.js');
const { makeWASocket, useMultiFileAuthState, fetchLatestBaileysVersion, makeCacheableSignalKeyStore } = baileys;

const authDir = '/home/openclaw/.openclaw/credentials/whatsapp/default';
const { state, saveCreds } = await useMultiFileAuthState(authDir);
const { version } = await fetchLatestBaileysVersion();

console.log('Creds registered:', state.creds.registered);
console.log('Creds me:', JSON.stringify(state.creds.me));
console.log('Baileys version:', version);

const noop = {
  level: 'silent',
  trace() {}, debug() {}, info() {}, warn() {}, error() {}, fatal() {},
  child() { return this; }
};

const sock = makeWASocket({
  auth: {
    creds: state.creds,
    keys: makeCacheableSignalKeyStore(state.keys, noop)
  },
  version,
  printQRInTerminal: false,
  browser: ['DebugTest', 'Chrome', '1.0'],
  syncFullHistory: false,
  shouldSyncHistoryMessage: () => true,
  markOnlineOnConnect: true,
});

const allEvents = [
  'connection.update',
  'creds.update',
  'messages.upsert',
  'messages.update',
  'messages.delete',
  'messages.reaction',
  'messaging-history.set',
  'chats.upsert',
  'chats.update',
  'chats.delete',
  'contacts.upsert',
  'contacts.update',
  'presence.update',
  'groups.upsert',
  'groups.update',
  'group-participants.update',
  'labels.association',
  'labels.edit',
];

for (const ev of allEvents) {
  sock.ev.on(ev, (data) => {
    const summary = JSON.stringify(data).substring(0, 500);
    console.log(`[EVENT ${new Date().toISOString()}] ${ev}: ${summary}`);
  });
}
sock.ev.on('creds.update', saveCreds);

console.log('=== Waiting 90s for events. SEND A MESSAGE NOW! ===');
console.log('=== Buffer flush expected at ~20s mark ===');

setTimeout(() => {
  console.log('=== 30s mark — buffer should have flushed by now ===');
}, 30000);

setTimeout(() => {
  console.log('=== 60s mark — still listening ===');
}, 60000);

setTimeout(() => {
  console.log('=== 90s elapsed. Shutting down. ===');
  try { sock.end(undefined); } catch (e) { /* ignore */ }
  process.exit(0);
}, 90000);

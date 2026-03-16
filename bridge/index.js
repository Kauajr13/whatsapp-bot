const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys')
const { Boom } = require('@hapi/boom')
const axios = require('axios')
const pino = require('pino')
const qrcode = require('qrcode-terminal')

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'
const AUTH_DIR = process.env.AUTH_DIR || './auth'

const logger = pino({ level: 'silent' })

// ── Filtros de quem o bot responde ───────────────────────────────
//
// MODO: 'all' | 'whitelist' | 'groups_only' | 'contacts_only'
//
// 'all'           — responde todo mundo (comportamento atual)
// 'whitelist'     — responde apenas os números/grupos listados abaixo
// 'groups_only'   — responde apenas grupos
// 'contacts_only' — responde apenas contatos individuais
//
const MODE = 'whitelist'

// Números e grupos autorizados (usado apenas no modo 'whitelist')
// Formato número:  '5511999999999@s.whatsapp.net'
// Formato grupo:   '120363XXXXXXXXXX@g.us'
// Para pegar o JID de um grupo, ative o modo 'all' temporariamente
// e veja o log — o JID aparece no campo phone.
const WHITELIST = new Set([
    '120363358269939540@g.us',
])

function isAllowed(jid) {
    if (MODE === 'all') return true
    if (MODE === 'whitelist') return WHITELIST.has(jid)
    if (MODE === 'groups_only') return jid.endsWith('@g.us')
    if (MODE === 'contacts_only') return jid.endsWith('@s.whatsapp.net')
    return false
}

async function sendToBackend(phone, message, name) {
    try {
        const res = await axios.post(`${BACKEND_URL}/webhook/message`, {
            phone,
            message,
            name: name || null
        })
        return res.data.response
    } catch (err) {
        console.error('Backend error:', err.message)
        return null
    }
}

async function connectToWhatsApp() {
    const { version } = await fetchLatestBaileysVersion()
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR)

    const sock = makeWASocket({
        version,
        auth: state,
        logger,
        browser: ['WhatsApp Bot', 'Chrome', '1.0.0'],
        connectTimeoutMs: 60000,
        defaultQueryTimeoutMs: 60000,
        keepAliveIntervalMs: 10000,
    })

    sock.ev.on('creds.update', saveCreds)

    sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
        if (qr) {
            console.log('\nScan this QR code with your WhatsApp:\n')
            qrcode.generate(qr, { small: true })
        }

        if (connection === 'close') {
            const statusCode = new Boom(lastDisconnect?.error)?.output?.statusCode
            const loggedOut = statusCode === DisconnectReason.loggedOut

            console.log(`Connection closed (code: ${statusCode})`)

            if (loggedOut) {
                console.log('Logged out. Delete the auth/ folder and restart.')
            } else {
                console.log('Reconnecting in 5s...')
                setTimeout(connectToWhatsApp, 5000)
            }
        }

        if (connection === 'open') {
            console.log(`Connected to WhatsApp | Mode: ${MODE}`)
        }
    })

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
        if (type !== 'notify') return

        for (const msg of messages) {
            if (msg.key.fromMe) continue
            if (!msg.message) continue

            const phone = msg.key.remoteJid

            if (!isAllowed(phone)) {
                console.log(`[BLOCKED] ${phone}`)
                continue
            }

            const text = (
                msg.message.conversation ||
                msg.message.extendedTextMessage?.text ||
                msg.message.imageMessage?.caption ||
                ''
            ).trim()

            if (!text) continue

            const name = msg.pushName || null
            console.log(`[${new Date().toISOString()}] ${phone} (${name}): ${text.slice(0, 80)}`)

            const response = await sendToBackend(phone, text, name)

            if (response) {
                await sock.sendMessage(phone, { text: response })
                console.log(`[${new Date().toISOString()}] -> ${phone}: ${response.slice(0, 80)}`)
            }
        }
    })

    return sock
}

connectToWhatsApp().catch(err => {
    console.error('Fatal error:', err)
    process.exit(1)
})

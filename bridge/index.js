// suprime erros de descriptografia do Baileys que não afetam o funcionamento
const _consoleError = console.error
console.error = (...args) => {
    const msg = args.join(' ')
    if (msg.includes('Bad MAC') || msg.includes('Failed to decrypt') || msg.includes('Session error')) return
    _consoleError(...args)
}

const { 
    default: makeWASocket, 
    useMultiFileAuthState, 
    DisconnectReason, 
    fetchLatestBaileysVersion,
    makeCacheableSignalKeyStore,
    isJidGroup,
} = require('@whiskeysockets/baileys')
const { Boom } = require('@hapi/boom')
const axios = require('axios')
const pino = require('pino')
const qrcode = require('qrcode-terminal')
const NodeCache = require('node-cache')

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'
const AUTH_DIR = process.env.AUTH_DIR || './auth'

const msgRetryCounterCache = new NodeCache()
const logger = pino({ level: 'silent' })

const MODE = 'all'

const WHITELIST = new Set([
    'lid@lid',
])

const BOT_PREFIX = null

function isAllowed(jid) {
    if (MODE === 'all') return true
    if (MODE === 'whitelist') return WHITELIST.has(jid)
    if (MODE === 'groups_only') return jid.endsWith('@g.us')
    if (MODE === 'contacts_only') return jid.endsWith('@s.whatsapp.net')
    return false
}

function shouldProcess(text) {
    if (!BOT_PREFIX) return true
    return text.toLowerCase().startsWith(BOT_PREFIX.toLowerCase())
}

function stripPrefix(text) {
    if (!BOT_PREFIX) return text
    return text.slice(BOT_PREFIX.length).trim()
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
        _consoleError('Backend error:', err.message)
        return null
    }
}

async function connectToWhatsApp() {
    const { version } = await fetchLatestBaileysVersion()
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR)

    const sock = makeWASocket({
        version,
        auth: {
            creds: state.creds,
            keys: makeCacheableSignalKeyStore(state.keys, logger),
        },
        msgRetryCounterCache,
        logger,
        browser: ['WhatsApp Bot', 'Chrome', '1.0.0'],
        connectTimeoutMs: 60000,
        defaultQueryTimeoutMs: 60000,
        keepAliveIntervalMs: 10000,
        syncFullHistory: false,
        markOnlineOnConnect: false,
        retryRequestDelayMs: 2000,
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
            const prefixInfo = BOT_PREFIX ? `prefix: ${BOT_PREFIX}` : 'no prefix'
            console.log(`Connected | Mode: ${MODE} | ${prefixInfo}`)
        }
    })

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
	console.log(`[DEBUG] upsert type=${type} count=${messages.length}`)
	    
	for (const msg of messages) {
	    console.log(`[DEBUG] fromMe=${msg.key.fromMe} jid=${msg.key.remoteJid} hasMsg=${!!msg.message}`)
		
	    if (msg.key.fromMe) continue
	    if (!msg.message) continue

	    const phone = msg.key.remoteJid
	    console.log(`[DEBUG] isAllowed(${phone})=${isAllowed(phone)} whitelist=${JSON.stringify([...WHITELIST])}`)
		
            if (!isAllowed(phone)) continue

            const raw = (
                msg.message.conversation ||
                msg.message.extendedTextMessage?.text ||
                msg.message.imageMessage?.caption ||
                ''
            ).trim()

            if (!raw) continue
            if (!shouldProcess(raw)) continue

            const text = stripPrefix(raw)
            if (!text) continue

            const name = msg.pushName || null
            console.log(`[IN]  ${phone} (${name}): ${raw.slice(0, 80)}`)

            const response = await sendToBackend(phone, text, name)
            if (!response) continue

            if (isJidGroup(phone)) {
                try {
                    const groupMeta = await sock.groupMetadata(phone)
                    const participants = groupMeta.participants.map(p => p.id)
                    await sock.assertSessions(participants, false)
                } catch (e) {}
            }

            try {
                await sock.sendMessage(phone, { text: response })
                console.log(`[OUT] ${phone}: ${response.slice(0, 80)}`)
            } catch (err) {
                _consoleError(`Send failed (${phone}): ${err.message}`)
            }
        }
    })

    return sock
}

connectToWhatsApp().catch(err => {
    _consoleError('Fatal error:', err)
    process.exit(1)
})

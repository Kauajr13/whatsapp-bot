const { default: makeWASocket, useMultiFileAuthState, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys')
const pino = require('pino')

const AUTH_DIR = process.env.AUTH_DIR || './auth'

async function connect() {
    const { version } = await fetchLatestBaileysVersion()
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR)

    const sock = makeWASocket({
        version,
        auth: state,
        logger: pino({ level: 'silent' }),
        browser: ['WhatsApp Bot', 'Chrome', '1.0.0'],
    })

    sock.ev.on('creds.update', saveCreds)

    await new Promise((resolve, reject) => {
        const timeout = setTimeout(
            () => reject(new Error('Timeout — make sure auth/ folder exists (run node index.js first)')),
            20000
        )
        sock.ev.on('connection.update', ({ connection }) => {
            if (connection === 'open') { clearTimeout(timeout); resolve() }
            if (connection === 'close') { clearTimeout(timeout); reject(new Error('Connection closed')) }
        })
    })

    return sock
}

async function main() {
    const sock = await connect()

    // ── Grupos ────────────────────────────────────────────────────
    console.log('\nGROUPS')
    console.log('─'.repeat(70))

    const groups = await sock.groupFetchAllParticipating()
    const groupList = Object.values(groups)
        .map(g => ({ name: g.subject, jid: g.id, members: g.participants.length }))
        .sort((a, b) => a.name.localeCompare(b.name))

    if (groupList.length === 0) {
        console.log('No groups found.')
    } else {
        groupList.forEach(g => {
            console.log(`Name    : ${g.name}`)
            console.log(`JID     : ${g.jid}`)
            console.log(`Members : ${g.members}`)
            console.log('─'.repeat(70))
        })
        console.log(`Total: ${groupList.length} group(s)`)
    }

    // ── Lookup por número ─────────────────────────────────────────
    console.log('\nCONTACT LOOKUP')
    console.log('─'.repeat(70))
    console.log('Baileys does not have access to your phone contacts.')
    console.log('To find a JID, pass the number as an argument:')
    console.log('')
    console.log('  node list_groups.js 5511999999999')
    console.log('')
    console.log('Format: country code + area code + number, no spaces or symbols.')
    console.log('─'.repeat(70))

    const numberArg = process.argv[2]
    if (numberArg) {
        const cleaned = numberArg.replace(/\D/g, '')
        console.log(`\nLooking up: ${cleaned}`)
        try {
            const [result] = await sock.onWhatsApp(cleaned)
            if (result?.exists) {
                console.log('Found!')
                console.log(`JID  : ${result.jid}`)
            } else {
                console.log(`Number ${cleaned} not found on WhatsApp.`)
            }
        } catch (e) {
            console.log(`Lookup failed: ${e.message}`)
        }
    }

    await sock.end()
    process.exit(0)
}

main().catch(err => {
    console.error('Error:', err.message)
    process.exit(1)
})

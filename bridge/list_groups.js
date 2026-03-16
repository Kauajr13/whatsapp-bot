const { default: makeWASocket, useMultiFileAuthState, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys')
const pino = require('pino')

const AUTH_DIR = process.env.AUTH_DIR || './auth'

async function listChats() {
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
        const timeout = setTimeout(() => reject(new Error('Timeout — make sure you are connected (auth/ folder exists)')), 20000)

        sock.ev.on('connection.update', async ({ connection }) => {
            if (connection === 'open') {
                clearTimeout(timeout)
                resolve()
            }
            if (connection === 'close') {
                clearTimeout(timeout)
                reject(new Error('Connection closed — run node index.js first to authenticate'))
            }
        })
    })

    console.log('\nFetching groups...\n')
    const groups = await sock.groupFetchAllParticipating()

    const groupList = Object.values(groups).map(g => ({
        name: g.subject,
        jid: g.id,
        participants: g.participants.length,
    }))

    groupList.sort((a, b) => a.name.localeCompare(b.name))

    if (groupList.length === 0) {
        console.log('No groups found.')
    } else {
        console.log('GROUPS')
        console.log('─'.repeat(70))
        groupList.forEach(g => {
            console.log(`Name : ${g.name}`)
            console.log(`JID  : ${g.jid}`)
            console.log(`Members: ${g.participants}`)
            console.log('─'.repeat(70))
        })
        console.log(`\nTotal: ${groupList.length} group(s)`)
    }

    console.log('\nFetching contacts...\n')
    const contacts = sock.store?.contacts || {}
    const contactList = Object.values(contacts)
        .filter(c => c.id.endsWith('@s.whatsapp.net') && c.name)
        .map(c => ({ name: c.name, jid: c.id }))
        .sort((a, b) => a.name.localeCompare(b.name))

    if (contactList.length > 0) {
        console.log('CONTACTS (with saved names)')
        console.log('─'.repeat(70))
        contactList.forEach(c => {
            console.log(`Name : ${c.name}`)
            console.log(`JID  : ${c.jid}`)
            console.log('─'.repeat(70))
        })
        console.log(`\nTotal: ${contactList.length} contact(s)`)
    } else {
        console.log('No contacts with saved names found.')
        console.log('Tip: contacts appear here after they send you a message or you chat with them.')
    }

    await sock.logout()
    process.exit(0)
}

listChats().catch(err => {
    console.error('Error:', err.message)
    process.exit(1)
})

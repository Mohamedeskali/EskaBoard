package org.eskaboard.app

import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.EOFException
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.net.URI
import java.security.MessageDigest
import java.security.SecureRandom

/**
 * A short connection of its own to the PC, for the floating buttons: the same
 * encrypted protocol as the page (challenge, hello with ctr 1, then sid and
 * an increasing ctr on every message), marked "oneshot" so the PC doesn't
 * push the board page out. It works whatever Android does to the page in the
 * background.
 *
 * Plain Kotlin and blocking: call [send] off the main thread.
 */
class PcLink private constructor(
    private val host: String,
    private val port: Int,
    private val token: String,
    private val key: ByteArray,
) {
    class Expired : IOException("this link no longer works")

    /**
     * Opens a session, sends [messages] (JSON objects as maps), and returns
     * once the PC answered a ping sent after them (it handles messages in
     * order, so they all arrived). Throws IOException otherwise.
     */
    fun send(messages: List<Map<String, Any?>>) {
        Socket().use { socket ->
            socket.connect(InetSocketAddress(host, port), CONNECT_MS)
            socket.soTimeout = READ_MS
            socket.tcpNoDelay = true
            val ws = WebSocket(BufferedInputStream(socket.getInputStream()), BufferedOutputStream(socket.getOutputStream()))
            ws.handshake(host, port, "/ws?t=$token")

            val challenge = unseal(ws.readText()) ?: throw IOException("bad challenge (wrong key?)")
            if (Json.string(challenge, "type") != "challenge") throw IOException("no challenge")
            val sid = Json.string(challenge, "sid") ?: throw IOException("no session id")
            var ctr = 0
            fun sendSealed(fields: Map<String, Any?>) {
                ctr++
                ws.writeText(seal(Json.encode(fields + mapOf("sid" to sid, "ctr" to ctr))))
            }
            sendSealed(mapOf("type" to "hello", "oneshot" to true))
            messages.forEach(::sendSealed)
            sendSealed(mapOf("type" to "ping"))
            val pingCtr = ctr
            while (true) {
                val answer = unseal(ws.readText()) ?: continue
                if (Json.string(answer, "type") == "pong" && Json.int(answer, "ctr") == pingCtr) break
            }
            ws.close()
        }
    }

    private fun seal(json: String): String {
        val nonce = ByteArray(SecretBox.NONCE_BYTES).also(random::nextBytes)
        return B64.encode(nonce + SecretBox.seal(json.toByteArray(Charsets.UTF_8), nonce, key))
    }

    private fun unseal(text: String): String? {
        val raw = B64.decode(text) ?: return null
        if (raw.size < SecretBox.NONCE_BYTES) return null
        val plain = SecretBox.open(raw.copyOfRange(SecretBox.NONCE_BYTES, raw.size), raw.copyOf(SecretBox.NONCE_BYTES), key)
        return plain?.toString(Charsets.UTF_8)
    }

    companion object {
        private const val CONNECT_MS = 4000
        private const val READ_MS = 10_000
        private val random = SecureRandom()

        /** The link in EskaBoard's QR code (http://IP:PORT/?t=TOKEN#k=KEY), or null. */
        fun fromUrl(url: String): PcLink? {
            val uri = try {
                URI(url)
            } catch (e: Exception) {
                return null
            }
            if (!uri.scheme.equals("http", ignoreCase = true) || uri.host.isNullOrEmpty()) return null
            val token = Regex("^t=([A-Za-z0-9_-]+)$").find(uri.rawQuery.orEmpty())?.groupValues?.get(1) ?: return null
            val keyText = Regex("^k=([A-Za-z0-9_-]+)$").find(uri.rawFragment.orEmpty())?.groupValues?.get(1) ?: return null
            val key = B64.decode(keyText, urlSafe = true)?.takeIf { it.size == SecretBox.KEY_BYTES } ?: return null
            return PcLink(uri.host, if (uri.port == -1) 80 else uri.port, token, key)
        }
    }
}

/** A minimal WebSocket client (RFC 6455): text frames, ping/pong, close. */
private class WebSocket(private val input: InputStream, private val output: OutputStream) {
    private val random = SecureRandom()

    fun handshake(host: String, port: Int, path: String) {
        val nonce = B64.encode(ByteArray(16).also(random::nextBytes))
        val request = "GET $path HTTP/1.1\r\n" +
            "Host: $host:$port\r\n" +
            "Upgrade: websocket\r\n" +
            "Connection: Upgrade\r\n" +
            "Sec-WebSocket-Key: $nonce\r\n" +
            "Sec-WebSocket-Version: 13\r\n\r\n"
        output.write(request.toByteArray(Charsets.ISO_8859_1))
        output.flush()

        val status = readLine()
        val headers = mutableMapOf<String, String>()
        while (true) {
            val line = readLine()
            if (line.isEmpty()) break
            val colon = line.indexOf(':')
            if (colon > 0) headers[line.substring(0, colon).trim().lowercase()] = line.substring(colon + 1).trim()
        }
        val code = status.split(' ').getOrNull(1)
        if (code == "403") throw PcLink.Expired()
        if (code != "101") throw IOException("no WebSocket: $status")
        val expected = B64.encode(
            MessageDigest.getInstance("SHA-1")
                .digest((nonce + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").toByteArray(Charsets.ISO_8859_1))
        )
        if (headers["sec-websocket-accept"] != expected) throw IOException("bad WebSocket accept")
    }

    private fun readLine(): String {
        val line = StringBuilder()
        while (true) {
            val b = input.read()
            if (b == -1) throw EOFException()
            if (b == '\n'.code) return line.toString().trimEnd('\r')
            if (line.length > 8192) throw IOException("header too long")
            line.append(b.toChar())
        }
    }

    /** The next text message (answers pings on the way). */
    fun readText(): String {
        val message = java.io.ByteArrayOutputStream()
        while (true) {
            val b0 = readByte()
            val b1 = readByte()
            val opcode = b0 and 0x0f
            val fin = b0 and 0x80 != 0
            var length = (b1 and 0x7f).toLong()
            if (length == 126L) length = ((readByte() shl 8) or readByte()).toLong()
            if (length == 127L) {
                length = 0
                repeat(8) { length = (length shl 8) or readByte().toLong() }
            }
            if (length > MAX_MESSAGE) throw IOException("message too large")
            val masked = b1 and 0x80 != 0
            val mask = if (masked) readFully(4) else null
            val payload = readFully(length.toInt())
            if (mask != null) for (i in payload.indices) payload[i] = (payload[i].toInt() xor mask[i % 4].toInt()).toByte()
            when (opcode) {
                0x0, 0x1 -> {
                    message.write(payload)
                    if (message.size() > MAX_MESSAGE) throw IOException("message too large")
                    if (fin) return message.toString("UTF-8")
                }
                0x8 -> throw IOException("closed by the PC")
                0x9 -> writeFrame(0xA, payload)
                else -> Unit // pong, binary: ignored
            }
        }
    }

    fun writeText(text: String) = writeFrame(0x1, text.toByteArray(Charsets.UTF_8))

    fun close() {
        try {
            writeFrame(0x8, byteArrayOf(0x03, 0xE8.toByte())) // 1000: normal
        } catch (e: IOException) {
            // already gone
        }
    }

    private fun writeFrame(opcode: Int, payload: ByteArray) {
        val header = java.io.ByteArrayOutputStream(14)
        header.write(0x80 or opcode)
        when {
            payload.size < 126 -> header.write(0x80 or payload.size)
            payload.size < 65536 -> {
                header.write(0x80 or 126)
                header.write(payload.size ushr 8)
                header.write(payload.size and 0xff)
            }
            else -> {
                header.write(0x80 or 127)
                val size = payload.size.toLong()
                for (shift in 56 downTo 0 step 8) header.write((size ushr shift).toInt() and 0xff)
            }
        }
        val mask = ByteArray(4).also(random::nextBytes)
        header.write(mask)
        output.write(header.toByteArray())
        val chunk = ByteArray(8192)
        var pos = 0
        while (pos < payload.size) {
            val n = minOf(chunk.size, payload.size - pos)
            for (i in 0 until n) chunk[i] = (payload[pos + i].toInt() xor mask[(pos + i) % 4].toInt()).toByte()
            output.write(chunk, 0, n)
            pos += n
        }
        output.flush()
    }

    private fun readByte(): Int {
        val b = input.read()
        if (b == -1) throw EOFException()
        return b
    }

    private fun readFully(n: Int): ByteArray {
        val out = ByteArray(n)
        var pos = 0
        while (pos < n) {
            val got = input.read(out, pos, n - pos)
            if (got == -1) throw EOFException()
            pos += got
        }
        return out
    }

    companion object {
        private const val MAX_MESSAGE = 1L shl 20 // the PC only sends short answers
    }
}

/** Base64 without android.util (plain Kotlin, works on every API level). */
internal object B64 {
    private const val CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    private val VALUES = IntArray(128) { -1 }.also { v ->
        CHARS.forEachIndexed { i, c -> v[c.code] = i }
        v['-'.code] = 62
        v['_'.code] = 63
    }

    fun encode(data: ByteArray): String {
        val out = StringBuilder((data.size + 2) / 3 * 4)
        var i = 0
        while (i + 2 < data.size) {
            val n = ((data[i].toInt() and 0xff) shl 16) or ((data[i + 1].toInt() and 0xff) shl 8) or (data[i + 2].toInt() and 0xff)
            out.append(CHARS[n ushr 18]).append(CHARS[(n ushr 12) and 63]).append(CHARS[(n ushr 6) and 63]).append(CHARS[n and 63])
            i += 3
        }
        val rest = data.size - i
        if (rest > 0) {
            val n = ((data[i].toInt() and 0xff) shl 16) or (if (rest == 2) (data[i + 1].toInt() and 0xff) shl 8 else 0)
            out.append(CHARS[n ushr 18]).append(CHARS[(n ushr 12) and 63])
            out.append(if (rest == 2) CHARS[(n ushr 6) and 63] else '=').append('=')
        }
        return out.toString()
    }

    /** Standard or (with [urlSafe]) URL-safe base64, padding optional; null if invalid. */
    fun decode(text: String, urlSafe: Boolean = false): ByteArray? {
        val body = text.trimEnd('=')
        if (body.length % 4 == 1) return null
        val out = ByteArray(body.length * 3 / 4)
        var bits = 0
        var count = 0
        var pos = 0
        for (c in body) {
            if (!urlSafe && (c == '-' || c == '_')) return null
            if (urlSafe && (c == '+' || c == '/')) return null
            val v = if (c.code < 128) VALUES[c.code] else -1
            if (v < 0) return null
            bits = (bits shl 6) or v
            count += 6
            if (count >= 8) {
                count -= 8
                out[pos++] = (bits ushr count).toByte()
            }
        }
        return out
    }
}

/** Just enough JSON for the protocol's flat messages. */
internal object Json {
    fun encode(fields: Map<String, Any?>): String {
        val out = StringBuilder()
        out.append('{')
        fields.entries.forEachIndexed { i, (name, value) ->
            if (i > 0) out.append(',')
            quote(name, out)
            out.append(':')
            when (value) {
                null -> out.append("null")
                is Boolean, is Int, is Long -> out.append(value.toString())
                else -> quote(value.toString(), out)
            }
        }
        return out.append('}').toString()
    }

    private fun quote(text: String, out: StringBuilder) {
        out.append('"')
        for (c in text) {
            when {
                c == '"' -> out.append("\\\"")
                c == '\\' -> out.append("\\\\")
                c < ' ' -> out.append(String.format("\\u%04x", c.code))
                else -> out.append(c)
            }
        }
        out.append('"')
    }

    /** A top-level string field of a flat JSON object (as the PC sends them). */
    fun string(json: String, name: String): String? =
        Regex("\"${Regex.escape(name)}\"\\s*:\\s*\"([^\"\\\\]*)\"").find(json)?.groupValues?.get(1)

    fun int(json: String, name: String): Int? =
        Regex("\"${Regex.escape(name)}\"\\s*:\\s*(-?\\d+)").find(json)?.groupValues?.get(1)?.toIntOrNull()
}

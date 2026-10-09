package org.eskaboard.app

/**
 * NaCl's crypto_secretbox (XSalsa20 + Poly1305), the page's nacl.secretbox
 * and the PC's PyNaCl SecretBox: [seal] gives MAC (16 bytes) || ciphertext.
 * Plain Kotlin, so the floating buttons can talk to the PC without the page.
 */
object SecretBox {
    const val KEY_BYTES = 32
    const val NONCE_BYTES = 24
    const val MAC_BYTES = 16

    fun seal(message: ByteArray, nonce: ByteArray, key: ByteArray): ByteArray {
        val stream = stream(message.size + 32, nonce, key)
        val out = ByteArray(MAC_BYTES + message.size)
        for (i in message.indices) out[MAC_BYTES + i] = (message[i].toInt() xor stream[32 + i].toInt()).toByte()
        val mac = poly1305(out, MAC_BYTES, message.size, stream.copyOf(32))
        mac.copyInto(out, 0)
        return out
    }

    /** The message, or null if [box] was not sealed with this key and nonce. */
    fun open(box: ByteArray, nonce: ByteArray, key: ByteArray): ByteArray? {
        if (box.size < MAC_BYTES) return null
        val length = box.size - MAC_BYTES
        val stream = stream(length + 32, nonce, key)
        val mac = poly1305(box, MAC_BYTES, length, stream.copyOf(32))
        var diff = 0
        for (i in 0 until MAC_BYTES) diff = diff or (mac[i].toInt() xor box[i].toInt())
        if (diff != 0) return null
        return ByteArray(length) { (box[MAC_BYTES + it].toInt() xor stream[32 + it].toInt()).toByte() }
    }

    // ---- XSalsa20 ----

    private val SIGMA = intArrayOf(0x61707865, 0x3320646e, 0x79622d32, 0x6b206574)

    /** [length] bytes of XSalsa20 keystream. */
    private fun stream(length: Int, nonce: ByteArray, key: ByteArray): ByteArray {
        require(key.size == KEY_BYTES && nonce.size == NONCE_BYTES)
        val subkey = hsalsa20(key, nonce)
        val state = IntArray(16)
        state[0] = SIGMA[0]
        for (i in 0 until 4) state[1 + i] = le32(subkey, 4 * i)
        state[5] = SIGMA[1]
        state[6] = le32(nonce, 16)
        state[7] = le32(nonce, 20)
        state[10] = SIGMA[2]
        for (i in 0 until 4) state[11 + i] = le32(subkey, 16 + 4 * i)
        state[15] = SIGMA[3]
        val out = ByteArray(length)
        val block = IntArray(16)
        var counter = 0L
        var pos = 0
        while (pos < length) {
            state[8] = counter.toInt()
            state[9] = (counter ushr 32).toInt()
            state.copyInto(block)
            rounds(block)
            for (i in 0 until 16) {
                val word = block[i] + state[i]
                for (b in 0 until 4) {
                    if (pos + 4 * i + b < length) out[pos + 4 * i + b] = (word ushr (8 * b)).toByte()
                }
            }
            pos += 64
            counter++
        }
        return out
    }

    private fun hsalsa20(key: ByteArray, nonce: ByteArray): ByteArray {
        val x = IntArray(16)
        x[0] = SIGMA[0]
        for (i in 0 until 4) x[1 + i] = le32(key, 4 * i)
        x[5] = SIGMA[1]
        for (i in 0 until 4) x[6 + i] = le32(nonce, 4 * i)
        x[10] = SIGMA[2]
        for (i in 0 until 4) x[11 + i] = le32(key, 16 + 4 * i)
        x[15] = SIGMA[3]
        rounds(x)
        val out = ByteArray(32)
        intArrayOf(x[0], x[5], x[10], x[15], x[6], x[7], x[8], x[9]).forEachIndexed { i, w -> put32(out, 4 * i, w) }
        return out
    }

    /** Salsa20's 20 rounds, in place, without the final addition. */
    private fun rounds(x: IntArray) {
        repeat(10) {
            // columns
            x[4] = x[4] xor (x[0] + x[12]).rotateLeft(7)
            x[8] = x[8] xor (x[4] + x[0]).rotateLeft(9)
            x[12] = x[12] xor (x[8] + x[4]).rotateLeft(13)
            x[0] = x[0] xor (x[12] + x[8]).rotateLeft(18)
            x[9] = x[9] xor (x[5] + x[1]).rotateLeft(7)
            x[13] = x[13] xor (x[9] + x[5]).rotateLeft(9)
            x[1] = x[1] xor (x[13] + x[9]).rotateLeft(13)
            x[5] = x[5] xor (x[1] + x[13]).rotateLeft(18)
            x[14] = x[14] xor (x[10] + x[6]).rotateLeft(7)
            x[2] = x[2] xor (x[14] + x[10]).rotateLeft(9)
            x[6] = x[6] xor (x[2] + x[14]).rotateLeft(13)
            x[10] = x[10] xor (x[6] + x[2]).rotateLeft(18)
            x[3] = x[3] xor (x[15] + x[11]).rotateLeft(7)
            x[7] = x[7] xor (x[3] + x[15]).rotateLeft(9)
            x[11] = x[11] xor (x[7] + x[3]).rotateLeft(13)
            x[15] = x[15] xor (x[11] + x[7]).rotateLeft(18)
            // rows
            x[1] = x[1] xor (x[0] + x[3]).rotateLeft(7)
            x[2] = x[2] xor (x[1] + x[0]).rotateLeft(9)
            x[3] = x[3] xor (x[2] + x[1]).rotateLeft(13)
            x[0] = x[0] xor (x[3] + x[2]).rotateLeft(18)
            x[6] = x[6] xor (x[5] + x[4]).rotateLeft(7)
            x[7] = x[7] xor (x[6] + x[5]).rotateLeft(9)
            x[4] = x[4] xor (x[7] + x[6]).rotateLeft(13)
            x[5] = x[5] xor (x[4] + x[7]).rotateLeft(18)
            x[11] = x[11] xor (x[10] + x[9]).rotateLeft(7)
            x[8] = x[8] xor (x[11] + x[10]).rotateLeft(9)
            x[9] = x[9] xor (x[8] + x[11]).rotateLeft(13)
            x[10] = x[10] xor (x[9] + x[8]).rotateLeft(18)
            x[12] = x[12] xor (x[15] + x[14]).rotateLeft(7)
            x[13] = x[13] xor (x[12] + x[15]).rotateLeft(9)
            x[14] = x[14] xor (x[13] + x[12]).rotateLeft(13)
            x[15] = x[15] xor (x[14] + x[13]).rotateLeft(18)
        }
    }

    // ---- Poly1305 (26-bit limbs, as poly1305-donna) ----

    private fun poly1305(data: ByteArray, offset: Int, length: Int, key: ByteArray): ByteArray {
        val mask = 0x3ffffffL
        val t0 = u32(key, 0)
        val t1 = u32(key, 4)
        val t2 = u32(key, 8)
        val t3 = u32(key, 12)
        val r0 = t0 and 0x3ffffff
        val r1 = ((t0 ushr 26) or (t1 shl 6)) and 0x3ffff03
        val r2 = ((t1 ushr 20) or (t2 shl 12)) and 0x3ffc0ff
        val r3 = ((t2 ushr 14) or (t3 shl 18)) and 0x3f03fff
        val r4 = (t3 ushr 8) and 0x00fffff
        val s1 = r1 * 5
        val s2 = r2 * 5
        val s3 = r3 * 5
        val s4 = r4 * 5
        var h0 = 0L
        var h1 = 0L
        var h2 = 0L
        var h3 = 0L
        var h4 = 0L
        val block = ByteArray(16)
        var pos = 0
        while (pos < length) {
            val n = minOf(16, length - pos)
            val hibit: Long
            if (n == 16) {
                data.copyInto(block, 0, offset + pos, offset + pos + 16)
                hibit = 1L shl 24
            } else {
                block.fill(0)
                data.copyInto(block, 0, offset + pos, offset + pos + n)
                block[n] = 1
                hibit = 0
            }
            val m0 = u32(block, 0)
            val m1 = u32(block, 4)
            val m2 = u32(block, 8)
            val m3 = u32(block, 12)
            h0 += m0 and mask
            h1 += ((m0 ushr 26) or (m1 shl 6)) and mask
            h2 += ((m1 ushr 20) or (m2 shl 12)) and mask
            h3 += ((m2 ushr 14) or (m3 shl 18)) and mask
            h4 += (m3 ushr 8) or hibit

            val d0 = h0 * r0 + h1 * s4 + h2 * s3 + h3 * s2 + h4 * s1
            var d1 = h0 * r1 + h1 * r0 + h2 * s4 + h3 * s3 + h4 * s2
            var d2 = h0 * r2 + h1 * r1 + h2 * r0 + h3 * s4 + h4 * s3
            var d3 = h0 * r3 + h1 * r2 + h2 * r1 + h3 * r0 + h4 * s4
            var d4 = h0 * r4 + h1 * r3 + h2 * r2 + h3 * r1 + h4 * r0
            var c = d0 ushr 26
            h0 = d0 and mask
            d1 += c; c = d1 ushr 26; h1 = d1 and mask
            d2 += c; c = d2 ushr 26; h2 = d2 and mask
            d3 += c; c = d3 ushr 26; h3 = d3 and mask
            d4 += c; c = d4 ushr 26; h4 = d4 and mask
            h0 += c * 5; c = h0 ushr 26; h0 = h0 and mask
            h1 += c
            pos += 16
        }

        // Fully carry h, then compute h - p and keep it if h >= p
        var c = h1 ushr 26; h1 = h1 and mask
        h2 += c; c = h2 ushr 26; h2 = h2 and mask
        h3 += c; c = h3 ushr 26; h3 = h3 and mask
        h4 += c; c = h4 ushr 26; h4 = h4 and mask
        h0 += c * 5; c = h0 ushr 26; h0 = h0 and mask
        h1 += c
        var g0 = h0 + 5; c = g0 ushr 26; g0 = g0 and mask
        var g1 = h1 + c; c = g1 ushr 26; g1 = g1 and mask
        var g2 = h2 + c; c = g2 ushr 26; g2 = g2 and mask
        var g3 = h3 + c; c = g3 ushr 26; g3 = g3 and mask
        var g4 = h4 + c - (1L shl 26)
        var select = (g4 ushr 63) - 1 // all ones if h >= p (g4 not negative)
        g0 = g0 and select; g1 = g1 and select; g2 = g2 and select; g3 = g3 and select; g4 = g4 and select
        select = select.inv()
        h0 = (h0 and select) or g0
        h1 = (h1 and select) or g1
        h2 = (h2 and select) or g2
        h3 = (h3 and select) or g3
        h4 = (h4 and select) or g4

        // h % 2^128 + s
        val w0 = (h0 or (h1 shl 26)) and 0xffffffffL
        val w1 = ((h1 ushr 6) or (h2 shl 20)) and 0xffffffffL
        val w2 = ((h2 ushr 12) or (h3 shl 14)) and 0xffffffffL
        val w3 = ((h3 ushr 18) or (h4 shl 8)) and 0xffffffffL
        var f = w0 + u32(key, 16)
        val out = ByteArray(16)
        put32(out, 0, f.toInt())
        f = w1 + u32(key, 20) + (f ushr 32)
        put32(out, 4, f.toInt())
        f = w2 + u32(key, 24) + (f ushr 32)
        put32(out, 8, f.toInt())
        f = w3 + u32(key, 28) + (f ushr 32)
        put32(out, 12, f.toInt())
        return out
    }

    private fun le32(b: ByteArray, i: Int): Int =
        (b[i].toInt() and 0xff) or ((b[i + 1].toInt() and 0xff) shl 8) or
            ((b[i + 2].toInt() and 0xff) shl 16) or ((b[i + 3].toInt() and 0xff) shl 24)

    private fun u32(b: ByteArray, i: Int): Long = le32(b, i).toLong() and 0xffffffffL

    private fun put32(b: ByteArray, i: Int, w: Int) {
        b[i] = w.toByte()
        b[i + 1] = (w ushr 8).toByte()
        b[i + 2] = (w ushr 16).toByte()
        b[i + 3] = (w ushr 24).toByte()
    }
}

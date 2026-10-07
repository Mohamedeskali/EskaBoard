package org.eskaboard.app

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/** The floating buttons' own link to the PC must match PyNaCl and the PC's protocol. */
class PcLinkTest {
    private fun hex(s: String) = ByteArray(s.length / 2) { s.substring(2 * it, 2 * it + 2).toInt(16).toByte() }

    @Test
    fun secretBoxMatchesPyNaCl() {
        // nacl.secret.SecretBox(KEY).encrypt(message, nonce)[24:] for each message length
        val key = hex(KEY)
        for ((n, nonce, box) in VECTORS) {
            val message = ByteArray(n) { ((it * 31 + 5) % 256).toByte() }
            assertArrayEquals("seal $n", hex(box), SecretBox.seal(message, hex(nonce), key))
            assertArrayEquals("open $n", message, SecretBox.open(hex(box), hex(nonce), key))
            val tampered = hex(box).also { it[it.size - 1] = (it[it.size - 1] + 1).toByte() }
            assertNull("tampered $n", SecretBox.open(tampered, hex(nonce), key))
        }
    }

    @Test
    fun base64RoundTrips() {
        for (n in 0..10) {
            val data = ByteArray(n) { (it * 37 + 200).toByte() }
            assertArrayEquals(data, B64.decode(B64.encode(data)))
        }
        assertEquals("aGk=", B64.encode("hi".toByteArray()))
        assertArrayEquals(byteArrayOf(-5, -1), B64.decode("-_8", urlSafe = true))
        assertNull(B64.decode("-_8"))
        assertNull(B64.decode("a!bc"))
    }

    @Test
    fun jsonIsEscaped() {
        assertEquals(
            """{"type":"text","text":"a\"b\\c\u000a","n":3,"ok":true}""",
            Json.encode(mapOf("type" to "text", "text" to "a\"b\\c\n", "n" to 3, "ok" to true)),
        )
        val challenge = """{"type": "challenge", "sid": "Ab-_9"}"""
        assertEquals("challenge", Json.string(challenge, "type"))
        assertEquals("Ab-_9", Json.string(challenge, "sid"))
        assertEquals(7, Json.int("""{"type": "pong", "ctr": 7}""", "ctr"))
    }

    @Test
    fun linkFromTheQrCode() {
        assertNotNull(PcLink.fromUrl("http://192.168.1.20:8765/?t=abc_DEF-1#k=OEhQz1muQUpmylv4C0tETrrtvx2fgykI7w-sToRGbHY"))
        assertNull(PcLink.fromUrl("http://192.168.1.20:8765/?t=abc#k=short"))
        assertNull(PcLink.fromUrl("http://192.168.1.20:8765/?t=a b#k=OEhQz1muQUpmylv4C0tETrrtvx2fgykI7w-sToRGbHY"))
        assertNull(PcLink.fromUrl("ftp://192.168.1.20/?t=abc#k=OEhQz1muQUpmylv4C0tETrrtvx2fgykI7w-sToRGbHY"))
    }

    companion object {
        private val KEY = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
        private val VECTORS = listOf(
            Triple(0, "00070e151c232a31383f464d545b626970777e858c939aa1", "262aa94edbc11ae9c68ffcdc0bac1e6a"),
            Triple(1, "01080f161d242b323940474e555c636a71787f868d949ba2", "eff1f9e1c7d4338268a1fb6793df9847eb"),
            Triple(15, "0f161d242b323940474e555c636a71787f868d949ba2a9b0", "f7748e42efdeb3873f2ae983215385a7ecffea27a40517be6673dce66d465a"),
            Triple(16, "10171e252c333a41484f565d646b727980878e959ca3aab1", "f83bdc48a6fb745ae6441947f96dc8c57ec4b19766d57b4b525ebd07c7c5ee94"),
            Triple(17, "11181f262d343b424950575e656c737a81888f969da4abb2", "ca8df14483ab5a47e8d91373158b65cfc997dd9a99af0a49d2f52586dfa82704dd"),
            Triple(63, "3f464d545b626970777e858c939aa1a8afb6bdc4cbd2d9e0", "48fe8ff2c15f026220ee90bfe684aafdd36db5db434a353b8ac70d04058f31538faa62922b7f0910292b74e738afc7a92c6ae9b019d4c2667c9fef5a66cbe653aa7c0bb5d57c9b18b25d22d940463f"),
            Triple(64, "40474e555c636a71787f868d949ba2a9b0b7bec5ccd3dae1", "2b77a74bda4bf99a279a653b6553acd5795993a58592c6e1f1de7ee571134eaeac627f51c7327e0bf2102419b01c4ca2523161de7d51adf752c292c6c65609910cbfffacaf1f89d3a6d800755935de5d"),
            Triple(65, "41484f565d646b727980878e959ca3aab1b8bfc6cdd4dbe2", "0b6f058960f479dcc08e08e0ef04bc57c304add8b4f142e14197d90f8be74da1d79727ec1dc3c30eb283cfb7e26b0e3f85390bcd7a8286b869ef6e45da20ca22c783fcc8f0fb6192fd6554b2e67fa8a71f"),
            Triple(200, "c8cfd6dde4ebf2f900070e151c232a31383f464d545b6269", "c38213df711024d74517d2ce08332d5ec3198954ac09075758262e03bd2a0589aa687410b9da23311f12349129a2c14e3a0e91c118cc9eea246203e1d5081c920be61a2f58f2e119d2dec15b59e4da6e53fc94371aa4220c4c067f2efe57e57a305eb662ac2fd49ef2a58c181cc3609e331a37702defd86b031356e204ce3325e6e754034236a7d85b0f607a121502d2b0a5e6fa15965781e606c3c927370925f27b5d9522b06bdc5e336f042c650267e34251540f276dc652cfb2e85c41250d46a0281098c7ac9ebe8b3e56586d491cd9417c7b33da3cc3"),
            Triple(1000, "e8eff6fd040b121920272e353c434a51585f666d747b8289", "b76f9f8e4666a68e97ee4b2e8b2ff6f16bdc17fa9e1319c37bfd1b27f34aeb178501cf68fc67388f767ca84c4d33b341ddf14b225f70a8fe572dff54146b73a3e1c329a701256bdb21dfb6b6902e6c5dca9883b211ae33cf2fd06b3136b020bf8a5b4b9c4e1d1a24d21fc1dc33225ca2195c308f91966aa367ba60ded78daee3455796c4eb7befe71e4d58c7b935a92ae53d94b2827961d828ef8c18418e7f6824389059c4305bf0241a08546c95ddb5b614a3aee3ffbfeb532d30a18ecbfd72e8986d98611f33134e3a8a9a200265c6e42c70271def4865a3940cc32b45a8d2926bf2d78aee1314e2bb510d39c549fa6e791e4ca7d3bf08a020267638a512dc6aff18aa61d280c8d951f905d9cc517b334743626880e20c6d2127e258d9942e9b68660893091adf86304a5755a3a897df18cf9dd124854e54f0838c1e9dd9e8a8c4c9ef707823982bd1e0d2da04ca6fb3a1273923dd9919c90541826b00f2c03653ea3f8a057b502860573e0c5e801fe965c0a1b4f7caffcda0b21bec3a8072c06fdb6f2339c5a0191f9268a628442502623860a17a55b0189da42353f1e3fadfdef8ea95ba9ba5f77fac74f59dbec2e7e38966fc859fb05ca0422faa1894629e0678e489367e8a30a3b4195951ae839af1270ca68d305f0b68b1386d3385e7aaafa1baf95c8e2bfa98f946144303d612a2e05b17ff5ec7039a746326b602e9bed697998a8a6f1bb9e8b9f66e430e182b16dd295dea3334c0bb65cbe7e54a7e4c29c6251568bc6548175798c790c33867b0afb50807fe389e30196196e19a0df2d295baf35393fec292fab69ac5f2d12daac212fada14d6ea4726d347d439216491d1b0cb832a8ea04a4e70a00ecead77ada489c895f80aa75400cbfd514a7fbf53a94055304d5ecc42a7365e080b2cd56471f94f36ad6f4570ef0aa3933424561a30306075455c68a5171449ed384f7864c5fb1ea65ee335ec87fb16d89521cba53d1a27a7a4394b1d0c02b26f5a24e65b0c608a39aa6287215508ff6913cf62c8a5e181f7d17c0250ae4385469ecbc6d117360c20bd23b214e8c23193ce25f457fa8751fcf72f784e1c639ab46a4e4bc9d52be4f9a5550c904db1bfce24b41df1347813fc575e5c4b59cacbdc406fc884c9c45a9a2feede8cadd4de281b60a17c8836583f0904eaa3c648aa58e2c22ecf6f905a0557161f63b555c7bfc7f31bf93cc62f3b7d784ea16b978b38e828caaa3ad88f95ba78ae887c7711cdde34232e522f71ff41d165458def4e7aa789622bcc306731354b6d3a3b9519ca74cde32dc03ce2f2bc5d56876a8555674996002e71f80090c64cf1105455746226c45f35e3f0dc8e5bbec76017e0f240ba622306df38755f424519503c7632f978bd29567b434f637202f36f23b969c342ab57ca4daa30878c98"),
        )
    }
}

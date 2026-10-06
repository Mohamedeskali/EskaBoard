package org.eskaboard.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class BoardLinkTest {
    private val url = "http://192.168.1.20:8765/?t=Ab_9-x#k=Zz09_-AbC"

    @Test
    fun parsesTheQrLink() {
        val link = BoardLink.parse(url)!!
        assertEquals(url, link.url)
        assertEquals("192.168.1.20:8765", link.label)
    }

    @Test
    fun findsTheLinkInSharedText() {
        assertEquals(url, BoardLink.parse("EskaBoard: $url.")!!.url)
        assertEquals(url, BoardLink.parse("  $url\n")!!.url)
    }

    @Test
    fun rejectsOtherLinks() {
        listOf(
            "",
            "192.168.1.20:8765",
            "http://192.168.1.20:8765/",
            "http://192.168.1.20:8765/?t=abc", // no key
            "http://192.168.1.20:8765/#k=abc", // no token
            "http://192.168.1.20:8765/other?t=abc#k=abc",
            "http://192.168.1.20:8765/?t=abc&x=1#k=abc",
            "http://192.168.1.20:8765/?t=a%20b#k=abc",
            "javascript:alert(1)//?t=abc#k=abc",
            "file:///sdcard/?t=abc#k=abc",
        ).forEach { assertNull(it, BoardLink.parse(it)) }
    }

    @Test
    fun staysOnThePc() {
        val link = BoardLink.parse(url)!!
        assertTrue(link.sameOrigin("http://192.168.1.20:8765/?t=new#k=new"))
        assertTrue(link.sameOrigin("http://192.168.1.20:8765/icon.png"))
        assertFalse(link.sameOrigin("http://192.168.1.21:8765/"))
        assertFalse(link.sameOrigin("http://192.168.1.20:8766/"))
        assertFalse(link.sameOrigin("https://192.168.1.20:8765/"))
        assertFalse(link.sameOrigin("https://example.com/"))
        assertFalse(link.sameOrigin("not a url"))
    }
}

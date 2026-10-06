package org.eskaboard.app

import java.net.URI
import java.net.URISyntaxException

/**
 * The link in EskaBoard's QR code: http://IP:PORT/?t=TOKEN#k=KEY (phonekb/app.py).
 * The token lets the PC accept the phone; the key, in the fragment, never leaves the phone.
 */
class BoardLink private constructor(private val uri: URI) {
    val url: String = uri.toString()

    /** "192.168.1.20:8765", to show the user which PC this is. */
    val label: String = if (uri.port == -1) uri.host else "${uri.host}:${uri.port}"

    /** True if [other] is a page of the same PC (the WebView stays on it). */
    fun sameOrigin(other: String): Boolean {
        val o = try {
            URI(other)
        } catch (e: URISyntaxException) {
            return false
        }
        return o.scheme.equals(uri.scheme, ignoreCase = true) &&
            o.host.equals(uri.host, ignoreCase = true) &&
            effectivePort(o) == effectivePort(uri)
    }

    companion object {
        // Shared text may hold more than the link, or end with punctuation
        private val LINK = Regex("""https?://[^\s#]+#k=[A-Za-z0-9_-]+""", RegexOption.IGNORE_CASE)
        private val TOKEN = Regex("""t=[A-Za-z0-9_-]+""")
        private val KEY = Regex("""k=[A-Za-z0-9_-]+""")

        /** The EskaBoard link in [text], or null if there is none. */
        fun parse(text: String): BoardLink? {
            val found = LINK.find(text.trim())?.value ?: return null
            val uri = try {
                URI(found)
            } catch (e: URISyntaxException) {
                return null
            }
            val ok = uri.scheme.lowercase() in setOf("http", "https") &&
                !uri.host.isNullOrEmpty() &&
                uri.rawPath.orEmpty() in setOf("", "/") &&
                TOKEN.matches(uri.rawQuery.orEmpty()) &&
                KEY.matches(uri.rawFragment.orEmpty())
            return if (ok) BoardLink(uri) else null
        }

        private fun effectivePort(u: URI): Int = when {
            u.port != -1 -> u.port
            u.scheme.equals("https", ignoreCase = true) -> 443
            else -> 80
        }
    }
}

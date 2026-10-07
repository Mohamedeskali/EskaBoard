package org.eskaboard.app

import android.content.Context
import android.os.Handler
import android.os.Looper
import java.io.IOException
import java.util.concurrent.Executors

/**
 * Sends the floating buttons' messages to the PC through their own short
 * connection (PcLink), one after the other, with the link last opened in
 * the app. Independent of the board page, which Android may freeze or stop
 * behind other apps.
 */
object PcSender {
    private val queue = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())

    /** [done] runs on the main thread: true once the PC got every message. */
    fun send(context: Context, messages: List<Map<String, Any?>>, done: (Boolean) -> Unit) {
        val link = MainActivity.lastLink(context.applicationContext)?.let { PcLink.fromUrl(it.url) }
        queue.execute {
            val ok = link != null && trySend(link, messages)
            main.post { done(ok) }
        }
    }

    private fun trySend(link: PcLink, messages: List<Map<String, Any?>>): Boolean {
        repeat(ATTEMPTS) { attempt ->
            try {
                link.send(messages)
                return true
            } catch (e: PcLink.Expired) {
                return false // a new QR is needed
            } catch (e: IOException) {
                // Wi-Fi waking up, or the PC busy: once more after a moment
                if (attempt < ATTEMPTS - 1) Thread.sleep(RETRY_MS)
            }
        }
        return false
    }

    private const val ATTEMPTS = 2
    private const val RETRY_MS = 1500L
}

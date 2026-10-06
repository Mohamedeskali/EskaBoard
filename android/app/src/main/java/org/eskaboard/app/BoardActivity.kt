package org.eskaboard.app

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Bitmap
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.webkit.JavascriptInterface
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.ProgressBar
import androidx.activity.enableEdgeToEdge

/** EskaBoard's phone page, full screen: the same page the browser shows. */
class BoardActivity : BaseActivity() {
    private lateinit var web: WebView
    private lateinit var loading: ProgressBar
    private val handler = Handler(Looper.getMainLooper())
    private var done = false
    private var loadFailed = false
    private var loadFailures = 0
    private var shown = false      // between onResume and onPause
    private var webPaused = false  // web.onPause() called

    // A screenshot from the floating button, waiting for the page to take it
    private val imageLock = Any()
    private var pendingImage: String? = null
    private var pendingDone: ((Boolean) -> Unit)? = null
    private var imageId = 0

    // Keys from the floating Enter button, waiting for the page's answer
    private val pendingKeys = mutableMapOf<Int, (Boolean) -> Unit>()
    private var keyId = 0

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val link = intent.getStringExtra(EXTRA_URL)?.let(BoardLink::parse)
        if (link == null) {
            finish()
            return
        }
        setContentView(R.layout.activity_board)
        padForSystemBars(findViewById(R.id.root))
        loading = findViewById(R.id.loading)
        web = findViewById(R.id.web)

        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true // the page remembers its language
            allowFileAccess = false
            allowContentAccess = false
            setGeolocationEnabled(false)
        }
        // What the page can ask the app (window.EskaBoardApp). The WebView only
        // ever shows the PC's page (shouldOverrideUrlLoading below).
        web.addJavascriptInterface(PageInterface(), "EskaBoardApp")
        web.webViewClient = object : WebViewClient() {
            // Only the PC's own page: there are no other links on it
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest) =
                !link.sameOrigin(request.url.toString())

            override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
                loadFailed = false
                loading.visibility = View.VISIBLE
            }

            override fun onPageFinished(view: WebView, url: String?) {
                if (loadFailed) return // keep the spinner over the error page
                loadFailures = 0
                web.visibility = View.VISIBLE
                loading.visibility = View.GONE
            }


            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (!request.isForMainFrame) return
                loadFailed = true
                // Right after the screen comes on, Wi-Fi may still be reconnecting:
                // try again for a while before giving up
                if (++loadFailures > LOAD_RETRIES) {
                    finishWith(RESULT_UNREACHABLE)
                    return
                }
                web.visibility = View.INVISIBLE
                handler.postDelayed({ if (!done) web.loadUrl(link.url) }, LOAD_RETRY_MS)
            }

            override fun onReceivedHttpError(
                view: WebView,
                request: WebResourceRequest,
                response: WebResourceResponse,
            ) {
                if (!request.isForMainFrame) return
                finishWith(
                    when (response.statusCode) {
                        403 -> RESULT_EXPIRED // EskaBoard was restarted, or "QR جديد" was pressed
                        429 -> RESULT_BLOCKED // too many bad tokens from this phone
                        else -> RESULT_UNREACHABLE
                    }
                )
            }
        }
        web.loadUrl(link.url)
        BoardBridge.attach(this)
        applyKeepAlive()
    }

    private inner class PageInterface {
        /** {"lang": "" | "ar" | "fr" | "en", "hidden": [tool names]} */
        @JavascriptInterface
        fun settings(): String = AppSettings.pageJson(this@BoardActivity)

        @JavascriptInterface
        fun openSettings() {
            handler.post { startActivity(Intent(this@BoardActivity, SettingsActivity::class.java)) }
        }

        /** The waiting screenshot (base64 PNG), handed over once. */
        @JavascriptInterface
        fun takeImage(): String? = synchronized(imageLock) {
            pendingImage.also { pendingImage = null }
        }

        /** True while a floating button runs: the page keeps its connection checked in the background. */
        @JavascriptInterface
        fun keepAlive(): Boolean = BoardBridge.keepAlive

        @JavascriptInterface
        fun keyResult(id: Int, ok: Boolean) {
            handler.post { finishKey(id, ok) }
        }

        @JavascriptInterface
        fun imageResult(ok: Boolean) {
            handler.post { finishImage(ok) }
        }

        // The link no longer works (EskaBoard restarted, "QR جديد", or 30 min
        // with no phone): back to the start screen to scan
        @JavascriptInterface
        fun linkExpired() {
            handler.post { finishWith(RESULT_EXPIRED) }
        }
    }

    /** Main thread: ask the page to send [base64Png] to the PC. */
    fun sendImage(base64Png: String, done: (Boolean) -> Unit) {
        finishImage(false) // an older one still waiting: give up on it
        synchronized(imageLock) { pendingImage = base64Png }
        pendingDone = done
        val id = ++imageId
        web.evaluateJavascript("window.eskaboardSendImage ? (window.eskaboardSendImage(), 'started') : 'no'") {
            if (it != "\"started\"") finishImage(false) // page not loaded (yet)
        }
        // The page checks the connection (reconnects if it dropped) for up to 12 s, then answers
        handler.postDelayed({ if (imageId == id) finishImage(false) }, IMAGE_TIMEOUT_MS)
    }

    /** Main thread: ask the page to press [key] on the PC (same as its own key buttons). */
    fun sendKey(key: String, done: (Boolean) -> Unit) {
        if (key !in KEYS) {
            done(false)
            return
        }
        val id = ++keyId
        pendingKeys[id] = done
        web.evaluateJavascript("window.eskaboardKey ? (window.eskaboardKey('$key', $id), 'started') : 'no'") {
            if (it != "\"started\"") finishKey(id, false) // page not loaded (yet), or an older PC page
        }
        handler.postDelayed({ finishKey(id, false) }, IMAGE_TIMEOUT_MS)
    }

    private fun finishKey(id: Int, ok: Boolean) {
        pendingKeys.remove(id)?.invoke(ok)
    }

    private fun finishImage(ok: Boolean) {
        val done = pendingDone ?: return
        pendingDone = null
        synchronized(imageLock) { pendingImage = null }
        done(ok)
    }

    private fun finishWith(result: Int) {
        if (done) return
        done = true
        setResult(result)
        finish()
    }

    /**
     * While a floating button (screenshot or Enter) runs, the page must stay
     * connected behind other apps so its taps reach the PC: the WebView is not
     * paused, and its renderer keeps its priority when not visible (otherwise
     * Android freezes it after a few seconds and the PC drops the connection).
     * The button's service keeps the app's process in the foreground. Without
     * one: the usual battery-friendly behaviour. Main thread; also called when
     * a button's service starts or stops (BoardBridge).
     */
    fun applyKeepAlive() {
        if (!::web.isInitialized) return
        val on = BoardBridge.keepAlive
        if (Build.VERSION.SDK_INT >= 26) {
            web.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, !on)
        }
        if (shown || on) {
            if (webPaused) {
                web.onResume()
                webPaused = false
            }
        } else if (!webPaused) {
            web.onPause()
            webPaused = true
        }
    }

    override fun onResume() {
        super.onResume()
        shown = true
        if (!::web.isInitialized) return
        applyKeepAlive()
        // Back from Settings: buttons and language, without reloading the page
        web.evaluateJavascript("window.eskaboardApplySettings && window.eskaboardApplySettings()", null)
        // Back from another app: the page checks its connection now
        // (reconnects silently) instead of waiting for its next retry
        web.evaluateJavascript("window.eskaboardResume && window.eskaboardResume()", null)
    }

    /** The page follows the new language itself; reloading it would cut the session. */
    override fun onLanguageChanged() = Unit

    override fun onPause() {
        shown = false
        applyKeepAlive()
        super.onPause()
    }

    override fun onDestroy() {
        BoardBridge.detach(this)
        handler.removeCallbacksAndMessages(null)
        finishImage(false)
        pendingKeys.values.toList().forEach { it(false) }
        pendingKeys.clear()
        if (::web.isInitialized) {
            web.stopLoading()
            web.destroy()
        }
        super.onDestroy()
    }

    companion object {
        const val EXTRA_URL = "url"
        const val RESULT_EXPIRED = RESULT_FIRST_USER
        const val RESULT_BLOCKED = RESULT_FIRST_USER + 1
        const val RESULT_UNREACHABLE = RESULT_FIRST_USER + 2
        private const val IMAGE_TIMEOUT_MS = 15_000L
        private const val LOAD_RETRIES = 10
        private const val LOAD_RETRY_MS = 2000L

        /** Keys a floating button may press (the page checks them too). */
        private val KEYS = setOf("enter")
    }
}

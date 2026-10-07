package org.eskaboard.app

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.graphics.Bitmap
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.ProgressBar
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts

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

    // The top bar's floating-button icons turn them on and off from here
    private val floating = FloatingSetup(this) { floatingChanged() }

    // The page's "Files" button: Android's picker, then the chosen files back to the page
    private var fileCallback: ValueCallback<Array<Uri>>? = null
    private val pickFiles = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val data = result.data
        val uris = if (result.resultCode != RESULT_OK || data == null) {
            null
        } else {
            data.clipData?.let { clip -> Array(clip.itemCount) { clip.getItemAt(it).uri } }
                ?: data.data?.let { arrayOf(it) }
        }
        fileCallback?.onReceiveValue(uris)
        fileCallback = null
    }

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
        web.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                view: WebView,
                callback: ValueCallback<Array<Uri>>,
                params: FileChooserParams,
            ): Boolean {
                fileCallback?.onReceiveValue(null) // an earlier picker never answered
                fileCallback = callback
                val pick = Intent(Intent.ACTION_GET_CONTENT)
                    .addCategory(Intent.CATEGORY_OPENABLE)
                    .setType("*/*")
                    .putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.mode == FileChooserParams.MODE_OPEN_MULTIPLE)
                return try {
                    pickFiles.launch(pick)
                    true
                } catch (e: ActivityNotFoundException) {
                    fileCallback = null
                    false
                }
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

        /** {"shot": bool, "enter": bool}: which floating buttons run (the top bar's icons). */
        @JavascriptInterface
        fun floatingState(): String =
            """{"shot":${ShotService.running},"enter":${EnterService.running}}"""

        /** "shot" or "enter": turn that floating button on (asking for permissions) or off. */
        @JavascriptInterface
        fun toggleFloating(kind: String) {
            val which = when (kind) {
                "shot" -> FloatingSetup.Kind.SHOT
                "enter" -> FloatingSetup.Kind.ENTER
                else -> return
            }
            handler.post { floating.toggle(which) }
        }

        /** True while a floating button runs: the page keeps its connection checked in the background. */
        @JavascriptInterface
        fun keepAlive(): Boolean = BoardBridge.keepAlive

        // The link no longer works (EskaBoard restarted, "QR جديد", or 30 min
        // with no phone): back to the start screen to scan
        @JavascriptInterface
        fun linkExpired() {
            handler.post { finishWith(RESULT_EXPIRED) }
        }
    }

    /** Main thread: a floating button pressed a key on the PC; in live mode the page starts a new text. */
    fun keySent() {
        if (::web.isInitialized) web.evaluateJavascript("window.eskaboardKeySent && window.eskaboardKeySent()", null)
    }

    private fun finishWith(result: Int) {
        if (done) return
        done = true
        setResult(result)
        finish()
    }

    /** Main thread: a floating button was turned on or off. */
    fun floatingChanged() {
        applyKeepAlive()
        if (::web.isInitialized) {
            web.evaluateJavascript("window.eskaboardApplySettings && window.eskaboardApplySettings()", null)
        }
    }

    /**
     * While a floating button (screenshot or Enter) runs, the page stays
     * connected behind other apps, ready when the user comes back (the buttons
     * themselves use their own connection, PcSender): the WebView is not
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
        private const val LOAD_RETRIES = 10
        private const val LOAD_RETRY_MS = 2000L
    }
}

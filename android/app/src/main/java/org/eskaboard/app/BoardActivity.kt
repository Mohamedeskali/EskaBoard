package org.eskaboard.app

import android.annotation.SuppressLint
import android.graphics.Bitmap
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
import androidx.activity.ComponentActivity
import androidx.activity.enableEdgeToEdge

/** EskaBoard's phone page, full screen: the same page the browser shows. */
class BoardActivity : ComponentActivity() {
    private lateinit var web: WebView
    private lateinit var loading: ProgressBar
    private val handler = Handler(Looper.getMainLooper())
    private var done = false
    private var loadFailed = false
    private var loadFailures = 0

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
        // The page calls this when the link no longer works (EskaBoard restarted,
        // "QR جديد", or 30 min with no phone): back to the start screen to scan
        web.addJavascriptInterface(object {
            @JavascriptInterface
            fun linkExpired() {
                handler.post { finishWith(RESULT_EXPIRED) }
            }
        }, "EskaBoardApp")
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
    }

    private fun finishWith(result: Int) {
        if (done) return
        done = true
        setResult(result)
        finish()
    }

    override fun onResume() {
        super.onResume()
        if (!::web.isInitialized) return
        web.onResume()
        // Back from another app: the page checks its connection now
        // (reconnects silently) instead of waiting for its next retry
        web.evaluateJavascript("window.eskaboardResume && window.eskaboardResume()", null)
    }

    override fun onPause() {
        if (::web.isInitialized) web.onPause()
        super.onPause()
    }

    override fun onDestroy() {
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

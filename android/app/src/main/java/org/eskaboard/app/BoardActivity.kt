package org.eskaboard.app

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.ProgressBar
import androidx.activity.ComponentActivity
import androidx.activity.enableEdgeToEdge
import androidx.annotation.RequiresApi

/** EskaBoard's phone page, full screen: the same page the browser shows. */
class BoardActivity : ComponentActivity() {
    private lateinit var web: WebView
    private lateinit var loading: ProgressBar
    private var done = false
    private var loadRetries = 0
    private val handler = Handler(Looper.getMainLooper())

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
        web.webViewClient = object : WebViewClient() {
            // Only the PC's own page: there are no other links on it
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest) =
                !link.sameOrigin(request.url.toString())

            override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
                loading.visibility = View.VISIBLE
            }

            override fun onPageFinished(view: WebView, url: String?) {
                loading.visibility = View.GONE
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (!request.isForMainFrame) return
                // Back from the background, Wi-Fi may take a moment to return
                if (loadRetries < LOAD_RETRIES) {
                    loadRetries++
                    handler.postDelayed({ if (!done) web.loadUrl(link.url) }, RETRY_DELAY_MS)
                } else {
                    finishWith(RESULT_UNREACHABLE)
                }
            }

            // Android may end the page's process while the app is in the
            // background; reload it instead of letting the app crash
            @RequiresApi(Build.VERSION_CODES.O)
            override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
                if (!done) recreate()
                return true
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
        if (::web.isInitialized) {
            web.onResume()
            // Reconnect now if the link dropped while the app was in the background
            web.evaluateJavascript("window.eskaWake && window.eskaWake()", null)
        }
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
        private const val LOAD_RETRIES = 4
        private const val RETRY_DELAY_MS = 1500L
    }
}

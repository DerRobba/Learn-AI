package com.malte_hinrichs.learn_ai

import android.Manifest
import android.app.DownloadManager
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.View
import android.webkit.*
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.Toolbar
import androidx.core.content.ContextCompat
import com.google.firebase.messaging.FirebaseMessaging


class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private var filePathCallback: ValueCallback<Array<Uri>>? = null

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { perms ->
            if (perms.values.any { !it }) {
                Toast.makeText(this, "Berechtigungen erforderlich für Downloads", Toast.LENGTH_LONG).show()
            }
        }

    private val filePickerLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            val data: Intent? = result.data
            val uris = if (data == null || data.data == null) arrayOf() else arrayOf(data.data!!)
            filePathCallback?.onReceiveValue(uris)
            filePathCallback = null
        }

    inner class AndroidBridge {
        @JavascriptInterface
        fun setNtfyTopic(topic: String) {
            if (topic.isNotEmpty()) {
                Log.d("NtfyBridge", "Starting ntfy service for topic: $topic")
                startNtfyService(topic)
            }
        }
    }

    private fun startNtfyService(userTopic: String = "") {
        val intent = Intent(this, NtfyListenerService::class.java)
        if (userTopic.isNotEmpty()) {
            intent.putExtra(NtfyListenerService.EXTRA_USER_TOPIC, userTopic)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val toolbar = findViewById<Toolbar>(R.id.toolbar)
        setSupportActionBar(toolbar)
        supportActionBar?.setDisplayShowTitleEnabled(false)

        window.statusBarColor = getColor(R.color.black)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
        }

        // Request notification permission (Android 13+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                permissionLauncher.launch(arrayOf(Manifest.permission.POST_NOTIFICATIONS))
            }
        }

        webView = findViewById(R.id.webView)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            @Suppress("DEPRECATION")
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            useWideViewPort = true
            loadWithOverviewMode = true
            cacheMode = WebSettings.LOAD_DEFAULT
            allowContentAccess = true
            allowFileAccess = true
        }

        webView.apply {
            setBackgroundColor(Color.WHITE)
            setLayerType(View.LAYER_TYPE_HARDWARE, null)
        }

        // Register JS bridge so the web app can pass the user's ntfy topic to us
        webView.addJavascriptInterface(AndroidBridge(), "AndroidApp")

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                return false
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                // Ask the server for this user's personal ntfy topic and forward it to the service
                view?.evaluateJavascript(
                    """
                    (function() {
                        fetch('/api/ntfy-topic')
                            .then(function(r) { return r.json(); })
                            .then(function(data) {
                                if (data && data.topic && typeof AndroidApp !== 'undefined') {
                                    AndroidApp.setNtfyTopic(data.topic);
                                }
                            })
                            .catch(function() {});
                    })();
                    """.trimIndent(),
                    null
                )
            }
        }

        webView.setDownloadListener { url, _, _, _, _ ->
            startDownload(url)
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest) {
                runOnUiThread {
                    val needed = request.resources.mapNotNull {
                        when (it) {
                            PermissionRequest.RESOURCE_VIDEO_CAPTURE -> Manifest.permission.CAMERA
                            PermissionRequest.RESOURCE_AUDIO_CAPTURE -> Manifest.permission.RECORD_AUDIO
                            else -> null
                        }
                    }
                    if (needed.isNotEmpty()) permissionLauncher.launch(needed.toTypedArray())
                    request.grant(request.resources)
                }
            }

            override fun onShowFileChooser(wv: WebView?, fpc: ValueCallback<Array<Uri>>?, fcp: FileChooserParams?): Boolean {
                filePathCallback = fpc
                val intent = fcp?.createIntent() ?: return false
                try { filePickerLauncher.launch(intent) } catch (e: Exception) { return false }
                return true
            }
        }

        // Start ntfy service for global channel immediately, user topic added after login
        startNtfyService()

        // Upload FCM token to Flask if needed
        uploadFcmTokenIfNeeded()

        webView.loadUrl("https://dev.l-ai.pro?android_app=True")

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else finish()
            }
        })
    }

    private fun uploadFcmTokenIfNeeded() {
        FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
            val prefs = getSharedPreferences("fcm", MODE_PRIVATE)
            val needsUpload = prefs.getBoolean("needs_upload", true)
            val stored = prefs.getString("token", null)
            if (needsUpload || stored != token) {
                prefs.edit().putString("token", token).putBoolean("needs_upload", false).apply()
                // Inject JS to POST the token once the page is loaded
                webView.post {
                    webView.evaluateJavascript("""
                        (function() {
                            fetch('/api/fcm-token', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({token: '$token'})
                            }).catch(function(){});
                        })();
                    """.trimIndent(), null)
                }
            }
        }
    }

    private fun startDownload(url: String) {
        try {
            val request = DownloadManager.Request(Uri.parse(url))
            val fileName = URLUtil.guessFileName(url, null, "application/pdf")

            request.setMimeType("application/pdf")
            request.addRequestHeader("User-Agent", webView.settings.userAgentString)
            request.setTitle(fileName)
            request.setDescription("Arbeitsblatt Download")
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            request.setDestinationInExternalPublicDir(android.os.Environment.DIRECTORY_DOWNLOADS, fileName)

            val dm = getSystemService(DOWNLOAD_SERVICE) as DownloadManager
            dm.enqueue(request)
            Toast.makeText(this, "Download gestartet: $fileName", Toast.LENGTH_LONG).show()
        } catch (e: Exception) {
            Log.e("Download", "Fehler: ${e.message}")
        }
    }
}

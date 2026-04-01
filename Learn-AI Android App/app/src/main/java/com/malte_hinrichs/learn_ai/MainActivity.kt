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

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                return false
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

        webView.loadUrl("https://dev.l-ai.pro?android_app=True")

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else finish()
            }
        })
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

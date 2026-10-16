package com.vahed.hesabdari;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
import android.widget.Toast;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

public class MainActivity extends Activity {
    private WebView webView;
    private final Handler handler = new Handler();
    private boolean pageLoaded = false;
    private int attempts = 0;

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);

        webView = new WebView(this);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                pageLoaded = true;
            }
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                                        WebResourceError error) {
                if (request.isForMainFrame()) {
                    pageLoaded = false;
                }
            }
        });
        setContentView(webView);

        try {
            if (!Python.isStarted()) {
                Python.start(new AndroidPlatform(this));
            }
            String dbPath = getFilesDir().getAbsolutePath() + "/hesabdari.db";
            Python.getInstance().getModule("start").callAttr("start_server", dbPath);
            loadWhenReady();
        } catch (Exception e) {
            Toast.makeText(this, "خطا در شروع برنامه: " + e.getMessage(),
                           Toast.LENGTH_LONG).show();
        }
    }

    private void loadWhenReady() {
        handler.postDelayed(() -> {
            attempts++;
            webView.loadUrl("http://127.0.0.1:5000/");
            if (!pageLoaded && attempts < 12) {
                handler.postDelayed(this::loadWhenReady, 1500);
            }
        }, 1000);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}

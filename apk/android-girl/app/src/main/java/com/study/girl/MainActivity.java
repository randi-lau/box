package com.study.girl;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.view.KeyEvent;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
    private WebView webView;
    private boolean fetched = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        webView = new WebView(this);
        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);          // 应用依赖大量 JS
        ws.setDomStorageEnabled(true);           // 开启 localStorage 持久化
        ws.setAllowFileAccess(true);             // 允许读取 assets 内文件
        ws.setUseWideViewPort(true);
        ws.setLoadWithOverviewMode(true);
        ws.setBuiltInZoomControls(false);
        ws.setDisplayZoomControls(false);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                fetchRemoteContent();
            }
        });
        setContentView(webView);
        webView.loadUrl("file:///android_asset/index.html");
    }

    // 联网拉取最新内容并注入网页（原生层负责联网，规避 WebView 跨域/CORS 问题）
    private void fetchRemoteContent() {
        if (fetched) return;
        fetched = true;
        String raw = getString(R.string.content_url);
        if (raw == null || raw.isEmpty() || raw.startsWith("https://example.com")) return; // 占位地址不请求
        final String url = raw + (raw.indexOf('?') >= 0 ? "&" : "?") + "_=" + System.currentTimeMillis();
        new Thread(new Runnable() {
            @Override public void run() {
                HttpURLConnection conn = null;
                try {
                    URL u = new URL(url);
                    conn = (HttpURLConnection) u.openConnection();
                    conn.setConnectTimeout(8000);
                    conn.setReadTimeout(8000);
                    conn.setRequestProperty("Accept", "application/json");
                    int code = conn.getResponseCode();
                    if (code == 200) {
                        BufferedReader r = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8));
                        StringBuilder sb = new StringBuilder();
                        String line;
                        while ((line = r.readLine()) != null) sb.append(line);
                        String json = sb.toString();
                        // 转义后作为 JS 字符串传入，调用网页的合并函数
                        String esc = json.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "");
                        final String js = "window.__applyRemoteContent && window.__applyRemoteContent('" + esc + "')";
                        webView.post(new Runnable() { @Override public void run() { webView.evaluateJavascript(js, null); } });
                    }
                } catch (Exception e) {
                    // 离线或失败：保留内置/已缓存内容，不影响使用
                } finally {
                    if (conn != null) conn.disconnect();
                }
            }
        }).start();
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && webView.canGoBack()) {
            webView.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }
}

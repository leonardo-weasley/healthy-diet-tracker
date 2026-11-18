package com.hdt.diettracker;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.SocketTimeoutException;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Native bridge for OpenAI-compatible vision requests.
 *
 * <p>Calling the provider from Java avoids WebView CORS restrictions and keeps large base64
 * images out of fetch/XHR. The JS side registers {@code window.__hdtNativeAiResult(id, ok, payload)}.
 */
public class AiBridge {

    private final Activity activity;
    private final WebView webView;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean closed = new AtomicBoolean(false);

    public AiBridge(Activity activity, WebView webView) {
        this.activity = activity;
        this.webView = webView;
    }

    @JavascriptInterface
    public void chat(String requestId, String endpoint, String apiKey, String model,
                     String imageDataUrl, String prompt, String timeoutMs) {
        submit(requestId, endpoint, apiKey, model, imageDataUrl, prompt, timeoutMs, false);
    }

    @JavascriptInterface
    public void test(String requestId, String endpoint, String apiKey, String model, String timeoutMs) {
        submit(requestId, endpoint, apiKey, model, null,
                "Reply with the single word OK.", timeoutMs, true);
    }

    @JavascriptInterface
    public String getVersion() {
        return "1.0.0";
    }

    @JavascriptInterface
    public void openExternal(String url) {
        if (url == null) {
            return;
        }
        String lower = url.toLowerCase(Locale.ROOT);
        if (!lower.startsWith("http://") && !lower.startsWith("https://")) {
            return;
        }
        activity.runOnUiThread(() -> {
            try {
                Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                activity.startActivity(intent);
            } catch (Exception error) {
                Toast.makeText(activity, "无法打开链接", Toast.LENGTH_SHORT).show();
            }
        });
    }

    @JavascriptInterface
    public void toast(String message) {
        if (message == null) {
            return;
        }
        activity.runOnUiThread(() ->
                Toast.makeText(activity, message, Toast.LENGTH_SHORT).show());
    }

    private void submit(String requestId, String endpoint, String apiKey, String model,
                        String imageDataUrl, String prompt, String timeoutMs, boolean testOnly) {
        if (closed.get()) {
            return;
        }
        int parsedTimeout = 60_000;
        try {
            parsedTimeout = Math.max(10_000, Math.min(180_000, Integer.parseInt(timeoutMs.trim())));
        } catch (Exception ignored) {
            // keep the default
        }
        final int timeout = parsedTimeout;
        executor.execute(() -> {
            String payload;
            boolean ok;
            try {
                String body = buildRequestBody(model, prompt, imageDataUrl,
                        testOnly ? 16 : 2048, !testOnly);
                HttpResult result = post(endpoint, apiKey, body, timeout);
                // Some OpenAI-compatible providers reject response_format; retry once without it.
                if (!testOnly && result.status == 400 && result.body != null
                        && result.body.contains("response_format")) {
                    body = buildRequestBody(model, prompt, imageDataUrl, 2048, false);
                    result = post(endpoint, apiKey, body, timeout);
                }
                if (result.status >= 200 && result.status < 300) {
                    ok = true;
                    payload = result.body;
                } else {
                    ok = false;
                    payload = errorPayload(reasonFor(result.status), result.status,
                            messageFor(result.status), result.body);
                }
            } catch (SocketTimeoutException error) {
                ok = false;
                payload = errorPayload("timeout", 0, "请求超时，请检查网络或稍后重试。", "");
            } catch (Exception error) {
                ok = false;
                payload = errorPayload("network", 0,
                        "网络请求失败：" + safeMessage(error), "");
            }
            dispatch(requestId, ok, payload, testOnly);
        });
    }

    private String buildRequestBody(String model, String prompt, String imageDataUrl,
                                    int maxTokens, boolean jsonFormat) throws Exception {
        JSONObject body = new JSONObject();
        body.put("model", model == null ? "" : model.trim());

        JSONArray content = new JSONArray();
        JSONObject textPart = new JSONObject();
        textPart.put("type", "text");
        textPart.put("text", prompt == null ? "" : prompt);
        content.put(textPart);

        if (imageDataUrl != null && !imageDataUrl.isEmpty()) {
            JSONObject imageUrl = new JSONObject();
            imageUrl.put("url", imageDataUrl);
            JSONObject imagePart = new JSONObject();
            imagePart.put("type", "image_url");
            imagePart.put("image_url", imageUrl);
            content.put(imagePart);
        }

        JSONObject message = new JSONObject();
        message.put("role", "user");
        message.put("content", content);

        JSONArray messages = new JSONArray();
        messages.put(message);

        body.put("messages", messages);
        body.put("temperature", 0);
        body.put("max_tokens", maxTokens);
        if (jsonFormat) {
            JSONObject format = new JSONObject();
            format.put("type", "json_object");
            body.put("response_format", format);
        }
        return body.toString();
    }

    private static final class HttpResult {
        final int status;
        final String body;

        HttpResult(int status, String body) {
            this.status = status;
            this.body = body;
        }
    }

    private HttpResult post(String endpoint, String apiKey, String body, int timeout)
            throws Exception {
        String url = chatUrl(endpoint);
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        connection.setRequestMethod("POST");
        connection.setConnectTimeout(Math.min(timeout, 20_000));
        connection.setReadTimeout(timeout);
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("User-Agent", "HealthyDietTracker-Android/1.0");
        if (apiKey != null && !apiKey.isEmpty()) {
            connection.setRequestProperty("Authorization", "Bearer " + apiKey.trim());
        }
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        connection.setFixedLengthStreamingMode(bytes.length);
        try (OutputStream output = connection.getOutputStream()) {
            output.write(bytes);
        }

        int status = connection.getResponseCode();
        InputStream input = status >= 200 && status < 300
                ? connection.getInputStream()
                : connection.getErrorStream();
        String text = readAll(input);
        connection.disconnect();
        return new HttpResult(status, text);
    }

    private static String readAll(InputStream input) throws Exception {
        if (input == null) {
            return "";
        }
        try (InputStream stream = input;
             ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
            byte[] chunk = new byte[8192];
            int read;
            while ((read = stream.read(chunk)) != -1) {
                buffer.write(chunk, 0, read);
            }
            return buffer.toString("UTF-8");
        }
    }

    private static String chatUrl(String endpoint) {
        String base = endpoint == null ? "" : endpoint.trim();
        if (base.endsWith("/chat/completions")) {
            return base;
        }
        while (base.endsWith("/")) {
            base = base.substring(0, base.length() - 1);
        }
        return base + "/chat/completions";
    }

    private static String reasonFor(int status) {
        if (status == 401 || status == 403) return "auth";
        if (status == 402) return "insufficient_balance";
        if (status == 404) return "not_found";
        if (status == 429) return "rate_limited";
        if (status >= 500) return "provider_5xx";
        return "provider_4xx";
    }

    private static String messageFor(int status) {
        if (status == 401 || status == 403) return "API Key 无效或没有权限。";
        if (status == 402) return "账户余额不足。";
        if (status == 404) return "API 地址或模型不存在，请检查设置。";
        if (status == 429) return "请求过于频繁，请稍后重试。";
        if (status >= 500) return "AI 服务暂时不可用，请稍后重试。";
        return "AI 服务拒绝了请求，请检查 API 地址与模型。";
    }

    private static String errorPayload(String reason, int status, String message, String body) {
        try {
            JSONObject error = new JSONObject();
            error.put("reason", reason);
            error.put("status", status);
            error.put("message", message);
            if (body != null && !body.isEmpty()) {
                error.put("body", body.length() > 600 ? body.substring(0, 600) : body);
            }
            return error.toString();
        } catch (Exception ignored) {
            return "{\"reason\":\"unknown\",\"message\":\"请求失败\"}";
        }
    }

    private static String safeMessage(Exception error) {
        String message = error.getMessage();
        if (message == null || message.isEmpty()) {
            return error.getClass().getSimpleName();
        }
        return message.length() > 200 ? message.substring(0, 200) : message;
    }

    private void dispatch(String requestId, boolean ok, String payload, boolean testOnly) {
        if (closed.get() || webView == null) {
            return;
        }
        String callback = testOnly ? "__hdtNativeAiTest" : "__hdtNativeAiResult";
        String script = "window." + callback + "(" + JSONObject.quote(requestId) + ","
                + (ok ? "true" : "false") + "," + JSONObject.quote(payload) + ");";
        activity.runOnUiThread(() -> {
            if (webView != null) {
                webView.evaluateJavascript(script, null);
            }
        });
    }

    public void shutdown() {
        closed.set(true);
        executor.shutdownNow();
    }
}

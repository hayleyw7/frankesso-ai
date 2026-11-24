package app.frankesso.android;

import android.app.Activity;
import android.content.res.ColorStateList;
import android.content.res.Configuration;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.graphics.drawable.StateListDrawable;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

public final class MainActivity extends Activity {
    private static final String MODEL_FILENAME = "qwen2.5-0.5b-instruct-q4_k_m.gguf";
    private static final long COPY_RESERVE_BYTES = 32L * 1024 * 1024;
    private static final Object MODEL_SETUP_LOCK = new Object();
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final AtomicBoolean closing = new AtomicBoolean();
    private final ChatPrompt chat = new ChatPrompt();
    private NativeModel model; // Worker-owned.
    private Path modelPath;
    private LinearLayout page;
    private ImageView bunny;
    private TextView title;
    private TextView subtitle;
    private TextView messageLabel;
    private boolean dark;
    private TextView status;
    private TextView transcript;
    private ScrollView scroll;
    private EditText composer;
    private Button retryButton;
    private Button clearButton;
    private Button sendButton;
    private boolean busy;
    private boolean ready;
    private ReplyInProgress generation;

    private static final class ReplyInProgress {
        final String input;
        final String transcriptStart;
        final boolean nativeReply;
        final AtomicBoolean canceled = new AtomicBoolean();
        String shown = "";

        ReplyInProgress(String input, String transcriptStart, boolean nativeReply) {
            this.input = input;
            this.transcriptStart = transcriptStart;
            this.nativeReply = nativeReply;
        }
    }

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        modelPath = getNoBackupFilesDir().toPath().resolve(MODEL_FILENAME);
        page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(16), dp(14), dp(16), dp(12));
        if (Build.VERSION.SDK_INT >= 30) {
            page.setOnApplyWindowInsetsListener((view, insets) -> {
                var system = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                var ime = insets.getInsets(WindowInsets.Type.ime());
                view.setPadding(dp(16) + system.left, dp(14) + system.top,
                        dp(16) + system.right, dp(12) + Math.max(system.bottom, ime.bottom));
                return WindowInsets.CONSUMED;
            });
            page.setFitsSystemWindows(false);
            getWindow().setDecorFitsSystemWindows(false);
        }

        // Same information order as desktop: brand, status, transcript, message, actions.
        LinearLayout header = row();
        bunny = new ImageView(this);
        header.addView(bunny, new LinearLayout.LayoutParams(dp(42), dp(42)));
        LinearLayout brand = new LinearLayout(this);
        brand.setOrientation(LinearLayout.VERTICAL);
        brand.setPadding(dp(12), 0, 0, 0);
        title = label("Frankesso", 20);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        brand.addView(title);
        subtitle = label("Offline chat", 13);
        brand.addView(subtitle);
        header.addView(brand, new LinearLayout.LayoutParams(0, -2, 1));
        page.addView(header);

        status = label("", 14);
        status.setPadding(0, dp(10), 0, dp(6));
        status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        page.addView(status);

        retryButton = actionButton(false);
        retryButton.setText("Retry setup");
        retryButton.setOnClickListener(v -> prepareModel());
        page.addView(retryButton);

        scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setVerticalScrollBarEnabled(true);
        scroll.setClipToOutline(true);
        transcript = label("", 16);
        transcript.setTextIsSelectable(true);
        transcript.setPadding(dp(12), dp(10), dp(12), dp(10));
        scroll.addView(transcript, new ScrollView.LayoutParams(-1, -2));
        page.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));

        messageLabel = label("Message", 14);
        messageLabel.setPadding(0, dp(10), 0, dp(4));
        page.addView(messageLabel);

        composer = new EditText(this);
        composer.setId(View.generateViewId());
        messageLabel.setLabelFor(composer.getId());
        composer.setInputType(InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        composer.setGravity(Gravity.TOP | Gravity.START);
        composer.setMinLines(2);
        composer.setMaxLines(3);
        composer.setTextSize(16);
        composer.setPadding(dp(10), dp(7), dp(10), dp(7));
        composer.setImeOptions(EditorInfo.IME_FLAG_NO_EXTRACT_UI);
        // Physical keyboards follow desktop; on-screen keyboards can insert a line break.
        composer.setOnKeyListener((v, key, event) -> {
            if ((key != KeyEvent.KEYCODE_ENTER && key != KeyEvent.KEYCODE_NUMPAD_ENTER)
                    || event.isShiftPressed() || event.isAltPressed() || event.isCtrlPressed()) return false;
            if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0) send();
            return true;
        });
        page.addView(composer, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout actions = row();
        actions.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
        clearButton = actionButton(false);
        clearButton.setText("New chat");
        clearButton.setOnClickListener(v -> {
            chat.clear();
            transcript.setText("");
            composer.setText("");
        });
        actions.addView(clearButton);
        sendButton = actionButton(true);
        sendButton.setText("Send");
        sendButton.setOnClickListener(v -> { if (generation != null) stopReply(); else send(); });
        actions.addView(sendButton);
        page.addView(actions);
        setContentView(page);
        applyTheme(getResources().getConfiguration().uiMode);
        prepareModel();
    }

    private void prepareModel() {
        if (busy || ready) return;
        busy = true;
        status.setText("Checking the offline model…");
        updateControls();
        worker.execute(() -> {
            try {
                synchronized (MODEL_SETUP_LOCK) {
                    if (closing.get()) return;
                    ModelImport.removeInterruptedCopies(modelPath.getParent());
                    if (!ModelImport.isVerified(modelPath, closing::get)) {
                        if (closing.get()) return;
                        long usable = modelPath.getParent().toFile().getUsableSpace();
                        if (usable < ModelImport.MODEL_BYTES + COPY_RESERVE_BYTES) {
                            complete(false, "Free at least 525 MB of device storage, then tap Retry setup.");
                            return;
                        }
                        unpackBundledModel();
                    }
                }
                if (closing.get()) return;
                onUi(() -> status.setText("Opening the verified model…"));
                loadModel();
            } catch (IOException e) {
                complete(false, "Could not prepare offline chat. Check storage and retry. If it still fails, check the installer download.");
            } catch (RuntimeException | LinkageError e) {
                complete(false, "Could not start the offline model on this phone.");
            }
        });
    }

    private void unpackBundledModel() throws IOException {
        onUi(() -> status.setText("Preparing offline chat… 0%"));
        try (InputStream input = getAssets().open(MODEL_FILENAME, android.content.res.AssetManager.ACCESS_STREAMING)) {
            int[] lastProgress = {0};
            ModelImport.copyVerified(input, modelPath, ModelImport.MODEL_BYTES, ModelImport.MODEL_SHA256,
                    closing::get, copied -> {
                        int percent = (int) (copied * 100 / ModelImport.MODEL_BYTES);
                        if (percent != 100 && percent - lastProgress[0] < 5) return;
                        lastProgress[0] = percent;
                        onUi(() -> status.setText("Preparing offline chat… " + percent + "%"));
                    });
        }
    }

    private void loadModel() {
        if (closing.get()) return;
        if (model == null) model = new NativeModel();
        model.open(modelPath.toString());
        complete(true, "Ready.");
    }

    private void send() {
        if (!ready || busy) return;
        String input = composer.getText().toString().trim();
        if (input.isEmpty()) return;
        LocalDate today = LocalDate.now();
        String prompt;
        try {
            prompt = chat.format(input, today);
        } catch (IllegalArgumentException e) {
            status.setText(e.getMessage());
            return;
        }
        composer.setText("");
        append("You", input);
        boolean test = "test".equalsIgnoreCase(input);
        String preset = test ? null : ChatPrompt.deviceDateReply(input, today);
        if (!test && preset == null) preset = ChatPrompt.personaReply(input);
        if (preset != null) {
            append("Frankesso", preset);
            chat.rememberTurn(input, preset);
            status.setText("Ready.");
            return;
        }
        ReplyInProgress reply = new ReplyInProgress(input, transcript.getText().toString(), !test);
        generation = reply;
        busy = true;
        status.setText("Starting a local reply…");
        updateControls();
        worker.execute(() -> {
            try {
                Consumer<String> progress = partial -> onUi(() -> {
                    if (generation == reply && !reply.canceled.get()) {
                        boolean firstText = reply.shown.isEmpty();
                        renderReply(reply, partial);
                        if (firstText) status.setText("Replying offline…");
                    }
                });
                String text = reply.nativeReply
                        ? model.reply(prompt, reply.canceled, progress)
                        : LocalReply.stream(ChatPrompt.TEST_REPLY, reply.canceled, progress);
                onUi(() -> finishReply(reply, text, null));
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                onUi(() -> finishReply(reply, "", "Reply stopped."));
            } catch (TimeoutException e) {
                onUi(() -> finishReply(reply, "", "Reply stopped at the one-minute limit. Try a shorter message."));
            } catch (RuntimeException | LinkageError e) {
                onUi(() -> finishReply(reply, "", "Couldn’t generate a reply. Try a shorter message or start a new chat."));
            }
        });
    }

    private void stopReply() {
        ReplyInProgress reply = generation;
        if (reply == null || reply.canceled.getAndSet(true)) return;
        if (reply.nativeReply) model.cancel();
        status.setText("Stopping the reply…");
        updateControls();
    }

    private void renderReply(ReplyInProgress reply, String text) {
        if (!reply.shown.equals(text)) {
            reply.shown = text;
            transcript.setText(reply.transcriptStart + "Frankesso\n" + text);
            scroll.post(() -> scroll.smoothScrollTo(0, transcript.getHeight()));
        }
    }

    private void finishReply(ReplyInProgress reply, String text, String failure) {
        if (generation != reply) return;
        if (!reply.canceled.get() && !text.isEmpty()) renderReply(reply, text);
        if (!reply.shown.isEmpty()) transcript.append("\n\n");
        if (reply.canceled.get()) {
            status.setText("Reply stopped.");
        } else if (failure != null) {
            status.setText(failure);
        } else if (text.isEmpty()) {
            status.setText("No reply. Try rephrasing.");
        } else {
            if (reply.nativeReply) chat.rememberTurn(reply.input, text);
            status.setText("Ready.");
        }
        generation = null;
        busy = false;
        updateControls();
    }

    private void complete(boolean available, String message) {
        onUi(() -> {
            ready = available;
            busy = false;
            status.setText(message);
            updateControls();
        });
    }

    private void onUi(Runnable task) {
        runOnUiThread(() -> { if (!closing.get()) task.run(); });
    }

    private void updateControls() {
        retryButton.setVisibility(!busy && !ready ? android.view.View.VISIBLE : android.view.View.GONE);
        clearButton.setEnabled(ready && !busy);
        sendButton.setText(generation == null ? "Send" : "Stop");
        sendButton.setEnabled(generation != null ? !generation.canceled.get() : ready && !busy);
        composer.setEnabled(ready && !busy);
    }

    private void append(String speaker, String message) {
        transcript.append(speaker + "\n" + message + "\n\n");
        if (transcript.length() > 24_000) {
            String text = transcript.getText().toString();
            int next = text.indexOf("\n\n", text.length() - 20_000);
            if (next >= 0) transcript.setText(text.substring(next + 2));
        }
        scroll.post(() -> scroll.smoothScrollTo(0, transcript.getHeight()));
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    private TextView label(String text, int size) {
        TextView label = new TextView(this);
        label.setText(text);
        label.setTextSize(size);
        return label;
    }

    private int backgroundColor() { return getColor(dark ? R.color.ink : R.color.cream); }
    private int foregroundColor() { return getColor(dark ? R.color.cream : R.color.ink); }
    private int mutedColor() { return getColor(dark ? R.color.cream_muted : R.color.ink_muted); }
    private int feedbackColor() { return getColor(dark ? R.color.cream_feedback : R.color.ink_feedback); }

    private static boolean systemUsesDark(int uiMode) {
        return (uiMode & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
    }

    @Override public void onConfigurationChanged(Configuration configuration) {
        super.onConfigurationChanged(configuration);
        if (dark != systemUsesDark(configuration.uiMode)) applyTheme(configuration.uiMode);
    }

    private void applyTheme(int uiMode) {
        dark = systemUsesDark(uiMode);
        page.setBackgroundColor(backgroundColor());
        for (TextView text : new TextView[]{title, subtitle, status, transcript, messageLabel, composer}) {
            text.setTextColor(foregroundColor());
        }
        bunny.setImageResource(dark ? R.drawable.frankesso_full_dark : R.drawable.frankesso_full);
        scroll.setBackground(field(false));
        transcript.setHighlightColor(feedbackColor());
        composer.setHighlightColor(feedbackColor());
        composer.setBackground(field(true));
        composer.setPadding(dp(10), dp(7), dp(10), dp(7));
        if (Build.VERSION.SDK_INT >= 29 && composer.getTextCursorDrawable() != null) {
            var cursor = composer.getTextCursorDrawable().mutate();
            cursor.setTint(foregroundColor());
            composer.setTextCursorDrawable(cursor);
        }
        for (Button button : new Button[]{retryButton, clearButton, sendButton}) {
            applyButtonTheme(button, button == sendButton);
        }

        if (Build.VERSION.SDK_INT >= 30) {
            if (Build.VERSION.SDK_INT < 35) {
                getWindow().setStatusBarColor(android.graphics.Color.TRANSPARENT);
                getWindow().setNavigationBarColor(android.graphics.Color.TRANSPARENT);
            }
            WindowInsetsController controller = getWindow().getInsetsController();
            int lightBars = WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS
                    | WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
            if (controller != null) controller.setSystemBarsAppearance(dark ? 0 : lightBars, lightBars);
        } else {
            // On older versions the OS draws opaque app-colored system bars.
            getWindow().setStatusBarColor(backgroundColor());
            getWindow().setNavigationBarColor(backgroundColor());
            View decor = getWindow().getDecorView();
            int lightBars = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            decor.setSystemUiVisibility((decor.getSystemUiVisibility() & ~lightBars) | (dark ? 0 : lightBars));
        }
    }

    private GradientDrawable surface(int color) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(color);
        shape.setCornerRadius(dp(10));
        return shape;
    }

    private GradientDrawable field(boolean input) {
        GradientDrawable shape = surface(backgroundColor());
        shape.setStroke(dp(1), input ? foregroundColor() : mutedColor());
        return shape;
    }

    private Button actionButton(boolean primary) {
        Button button = new Button(this);
        button.setAllCaps(false);
        applyButtonTheme(button, primary);
        button.setMinHeight(dp(48));
        LinearLayout.LayoutParams space = new LinearLayout.LayoutParams(-2, -2);
        space.setMargins(dp(4), dp(4), dp(4), dp(4));
        button.setLayoutParams(space);
        return button;
    }

    private void applyButtonTheme(Button button, boolean primary) {
        int[][] states = {{-android.R.attr.state_enabled}, {}};
        button.setTextColor(new ColorStateList(states,
                new int[]{mutedColor(), primary ? backgroundColor() : foregroundColor()}));
        GradientDrawable disabled = surface(backgroundColor());
        disabled.setStroke(dp(1), getColor(dark
                ? R.color.cream_disabled_outline : R.color.ink_disabled_outline));
        GradientDrawable enabled = surface(primary ? foregroundColor() : backgroundColor());
        if (!primary) enabled.setStroke(dp(1), foregroundColor());
        StateListDrawable fill = new StateListDrawable();
        fill.addState(states[0], disabled);
        fill.addState(states[1], enabled);
        button.setBackgroundTintList(null);
        int feedback = primary
                ? getColor(dark ? R.color.ink_feedback : R.color.cream_feedback) : feedbackColor();
        button.setBackground(new RippleDrawable(ColorStateList.valueOf(feedback), fill, null));
        button.setPadding(dp(12), 0, dp(12), 0);
    }

    private LinearLayout row() {
        LinearLayout row = new LinearLayout(this);
        row.setGravity(Gravity.CENTER_VERTICAL);
        return row;
    }

    @Override protected void onDestroy() {
        closing.set(true);
        if (generation != null) {
            generation.canceled.set(true);
            if (generation.nativeReply) model.cancel();
        }
        worker.execute(() -> { if (model != null) model.close(); });
        worker.shutdown();
        super.onDestroy();
    }
}

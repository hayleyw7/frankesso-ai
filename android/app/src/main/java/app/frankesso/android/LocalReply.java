package app.frankesso.android;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

/** Streams a fixed local answer through the same UI updates as native generation. */
final class LocalReply {
    interface Pause { void waitFor(long millis) throws InterruptedException; }

    static String stream(String text, AtomicBoolean canceled, Consumer<String> progress)
            throws InterruptedException {
        return stream(text, canceled, progress, Thread::sleep);
    }

    static String stream(String text, AtomicBoolean canceled, Consumer<String> progress, Pause pause)
            throws InterruptedException {
        int end = 0;
        while (!canceled.get() && end < text.length()) {
            if (end != 0) pause.waitFor(30);
            if (canceled.get()) break;
            for (int i = 0; i < 4 && end < text.length(); ++i) {
                end += Character.charCount(text.codePointAt(end));
            }
            progress.accept(text.substring(0, end));
        }
        return text.substring(0, end);
    }

    private LocalReply() { }
}

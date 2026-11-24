package app.frankesso.android;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

public final class NativeReplySmoke {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("Pass the verified Qwen GGUF path.");
        var model = new NativeModel();
        model.open(args[0]);
        try {
            var chat = new ChatPrompt();
            var first = new AtomicLong();
            long start = System.nanoTime();
            String text = model.reply(chat.format("Briefly describe how a seed grows."),
                    new AtomicBoolean(), partial -> first.compareAndSet(0, System.nanoTime()));
            long finished = System.nanoTime();
            if (text.isEmpty() || first.get() == 0 || first.get() >= finished) {
                throw new AssertionError("Missing generated reply or progressive output.");
            }
            System.out.printf("First visible text %d ms, completion %d ms from submission.%n",
                    millis(first.get() - start), millis(finished - start));

            try {
                model.reply(chat.format("Describe ivy."), new AtomicBoolean(), partial -> { }, 1);
                throw new AssertionError("Expected native deadline to end the reply.");
            } catch (TimeoutException expected) {
                System.out.println("Native timeout passed.");
            }

            var firstPartial = new CountDownLatch(1);
            var stopIssued = new CountDownLatch(1);
            var canceled = new AtomicBoolean();
            Thread stop = new Thread(() -> {
                try {
                    if (firstPartial.await(20, TimeUnit.SECONDS)) {
                        canceled.set(true);
                        model.cancel();
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                } finally {
                    stopIssued.countDown();
                }
            });
            stop.start();
            String stopped = model.reply(chat.format("List twenty ideas for a small herb garden."), canceled, partial -> {
                if (firstPartial.getCount() != 0) {
                    firstPartial.countDown();
                    try {
                        if (!stopIssued.await(3, TimeUnit.SECONDS)) {
                            throw new AssertionError("Concurrent stop request did not return.");
                        }
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        throw new AssertionError(e);
                    }
                }
            });
            stop.join();
            if (!canceled.get() || stopped.isEmpty()) throw new AssertionError("No partial reply to stop.");
            var next = model.reply(chat.format("Name one herb."), new AtomicBoolean(), partial -> { });
            if (next.isEmpty()) throw new AssertionError("Could not reply after cancellation.");
            System.out.println("Cross-thread stop and subsequent native reply passed.");
        } finally {
            model.close();
        }
    }

    private static long millis(long nanos) { return TimeUnit.NANOSECONDS.toMillis(nanos); }
}

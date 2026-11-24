package app.frankesso.android;

import java.time.LocalDateTime;
import java.util.concurrent.atomic.AtomicBoolean;

// Runs the APK's Java prompt and JNI inference against the exact bundled GGUF on a host.
public final class NativePromptRegression {
    private static final LocalDateTime CLOCK = LocalDateTime.of(2026, 11, 24, 1, 20, 58);

    public static void main(String[] args) throws Exception {
        var model = new NativeModel();
        model.open(args[0]);
        try {
            var chat = new ChatPrompt();
            report("ambiguous president", chat.clarificationReply("Who is the president?"));
            report("identity", ChatPrompt.capabilityReply("Who are you?"));
            report("file access", ChatPrompt.capabilityReply("Are you able to access files on my phone?"));
            report("device time", ChatPrompt.deviceClockReply("What time is it?", CLOCK, false));
            report("exact time follow-up", ChatPrompt.deviceClockReply("I want the literal exact time", CLOCK.plusMinutes(1), false));
            report("cat weight", infer(model, new ChatPrompt(), "how much does a cat weigh"));
            report("Jupiter false premise", infer(model, new ChatPrompt(), "Why is Jupiter smaller than Earth?"));
            report("Jupiter after identity", infer(model, chat, "Tell me two facts about Jupiter."));
            report("specific president without source", infer(model, new ChatPrompt(), "Who is the president of the USA?"));
            report("president with dated source", infer(model, new ChatPrompt(),
                    "A Norvia government notice dated May 1, 2024 lists Mira Vale as president. Who is president of Norvia now?"));
            report("generic you", infer(model, new ChatPrompt(), "What does it feel like when you ride a roller coaster?"));
        } finally {
            model.close();
        }
    }

    private static String infer(NativeModel model, ChatPrompt chat, String input) throws Exception {
        String direct = chat.clarificationReply(input);
        return direct != null ? direct : model.reply(chat.format(input, CLOCK, false), new AtomicBoolean(), partial -> { });
    }

    private static void report(String name, String text) {
        if (text == null || text.isBlank()) throw new AssertionError("No reply for " + name);
        System.out.println("CASE " + name + ": " + text.replace('\n', ' '));
    }
}

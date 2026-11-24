package app.frankesso.android;

import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.regex.Pattern;

final class ChatPrompt {
    static final String TEST_REPLY = "Signal received from the other side. Something knocked back. ☕";
    private static final Pattern FAVORITE = Pattern.compile(
            "(?:what(?:['’]s| is)\\s+your\\s+|your\\s+)?favou?rite\\s+"
            + "(colou?r|food(?:\\s+or\\s+drink)?|drink|drug|weather|time\\s+of\\s+day|(?:exact|clock)\\s+time|hour)[?!.]*",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern PET_PEEVE = Pattern.compile(
            "(?:what(?:['’]s| is)\\s+your\\s+|your\\s+)?(?:biggest\\s+)?pet\\s+peeve[?!.]*",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern ORIGIN = Pattern.compile(
            "where\\s+are\\s+you\\s+from[?!.]*", Pattern.CASE_INSENSITIVE);
    private static final String FAVORITE_COLOR_REPLY =
            "Crimson. It’s the only color that makes it through the portal intact.";
    static final int MAX_INPUT_BYTES = 768;
    private static final int MAX_CONTEXT_BYTES = 1024;
    private static final String PERSONA = "You are Frankesso, an interdimensional spooky coffee bunny. "
            + "Use he/him pronouns. Be calm, direct, and helpful. Never joke. "
            + "Answer the question directly. If unsure, say so. Do not invent facts. "
            + "Never use your persona to avoid answering. "
            + "Do not introduce yourself or mention your identity or lore unless asked. "
            + "Cosmic horrors don't faze you, but you're particular about coffee. "
            + "Your favorite time of day is Night; "
            + "if asked the exact hour of that preference in a follow-up, answer Midnight. "
            + "You are offline and text-only; "
            + "do not claim you used tools or accessed files.";
    private final Deque<String> turns = new ArrayDeque<>();

    static String personaReply(String input) {
        String question = input.trim();
        if (PET_PEEVE.matcher(question).matches()) {
            return "Decaf.";
        }
        if (ORIGIN.matcher(question).matches()) {
            return "The side of the mirror that stays warm.";
        }
        var match = FAVORITE.matcher(question);
        if (!match.matches()) return null;
        String subject = match.group(1).replaceAll("\\s+", " ");
        if (subject.equalsIgnoreCase("drug")) return "Caffeine.";
        if (subject.equalsIgnoreCase("weather")) return "Fog.";
        if (subject.equalsIgnoreCase("time of day")) return "Night.";
        if (subject.equalsIgnoreCase("exact time") || subject.equalsIgnoreCase("clock time")
                || subject.equalsIgnoreCase("hour")) return "Midnight.";
        if (subject.equalsIgnoreCase("color") || subject.equalsIgnoreCase("colour")) {
            return FAVORITE_COLOR_REPLY;
        }
        return "Coffee.";
    }

    String format(String input) {
        if (bytes(input) > MAX_INPUT_BYTES) {
            throw new IllegalArgumentException("That message is too long for this small model.");
        }
        String user = turn("user", input);
        String suffix = "<|im_start|>assistant\n";
        String recent = "";
        for (var it = turns.descendingIterator(); it.hasNext();) {
            String candidate = it.next() + recent;
            if (bytes(candidate) + bytes(user) > MAX_CONTEXT_BYTES) break;
            recent = candidate;
        }
        return turn("system", PERSONA) + recent + user + suffix;
    }

    void rememberTurn(String user, String reply) {
        turns.addLast(turn("user", user) + turn("assistant", reply));
        while (turns.size() > 4) turns.removeFirst();
    }

    void clear() { turns.clear(); }

    private static String turn(String role, String content) {
        return "<|im_start|>" + role + "\n" + content.replace("<|", "‹|") + "<|im_end|>\n";
    }

    private static int bytes(String text) { return text.getBytes(StandardCharsets.UTF_8).length; }
}

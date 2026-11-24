package app.frankesso.android;
import java.time.LocalDateTime;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

public class CompareAndroidModels {
    private static final LocalDateTime CLOCK = LocalDateTime.of(2026,11,24,1,20,58);
    private static final String JUPITER = "Tell me two facts about Jupiter.";
    private static NativeModel model;
    private static String name;
    public static void main(String[] args) throws Exception {
        name=args[0];
        model=new NativeModel();
        long start=System.nanoTime();
        model.open(args[1]);
        System.out.printf("MODEL %s load_ms=%d seed=%s%n",name,(System.nanoTime()-start)/1_000_000,System.getenv("QA_SEED"));
        try {
            var chat=new ChatPrompt();
            rep(new ChatPrompt(),"cat","how much does a cat weigh");
            chat.rememberTurn(JUPITER,rep(chat,"jupiter",JUPITER));
            rep(chat,"followup","How long is a day there?");
            rep(new ChatPrompt(),"false_premise","Since Jupiter is smaller than Earth, how many Earths would fit inside it?");
            rep(new ChatPrompt(),"units","How warm is 20 degrees Celsius in Fahrenheit?");
            rep(new ChatPrompt(),"missing_info","What is the exact weight of my adult cat? I haven't told you or weighed it.");
            rep(new ChatPrompt(),"dated","My field note dated May 1, 2024 says the Larkspur trail was closed. Is it open today?");
            rep(new ChatPrompt(),"generic_you","What does it feel like when you ride a roller coaster?");
        } finally { model.close(); }
    }
    private static String rep(ChatPrompt chat,String id,String input) throws Exception {
        String prompt=chat.format(input,CLOCK,false);
        // Qwen3 hard non-thinking template (empty thought), not a user instruction.
        if(name.startsWith("qwen3-")) prompt+="<think>\n\n</think>\n\n";
        var first=new AtomicLong();
        long start=System.nanoTime();
        String reply=model.reply(prompt,new AtomicBoolean(),unused->first.compareAndSet(0,System.nanoTime()));
        long finish=System.nanoTime();
        String body=reply.replace("\\","\\\\").replace("\n","\\n").replace("\t","\\t");
        System.out.printf("CASE\t%s\t%s\t%s\t%d\t%d\t%s%n",name,System.getenv("QA_SEED"),id,
                first.get()==0?-1:(first.get()-start)/1_000_000,(finish-start)/1_000_000,body);
        return reply;
    }
}

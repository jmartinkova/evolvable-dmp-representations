import java.io.ByteArrayInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import org.apache.jena.sys.JenaSystem;
import org.apache.jena.graph.Triple;
import org.apache.jena.sparql.core.Quad;
import org.apache.jena.riot.*;
import org.apache.jena.riot.system.StreamRDFBase;

/** In-memory streaming parse: no graph storage, disk I/O or JVM startup timed. */
public class ParseBenchmark {
    static class Counter extends StreamRDFBase {
        long triples = 0, quads = 0;
        @Override public void triple(Triple t) { triples++; }
        @Override public void quad(Quad q) { quads++; }
    }
    static void parse(byte[] data, Lang lang, String base, StreamRDFBase sink) {
        RDFParser.create().source(new ByteArrayInputStream(data))
            .lang(lang).base(base).parse(sink);
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 5) throw new IllegalArgumentException(
            "Usage: ParseBenchmark file syntax warmups measurements warmupSeconds");
        Path path = Path.of(args[0]).toAbsolutePath();
        int warmups = Integer.parseInt(args[2]);
        int measurements = Integer.parseInt(args[3]);
        double warmupSeconds = Double.parseDouble(args[4]);
        if (!Double.isFinite(warmupSeconds) || warmupSeconds < 0)
            throw new IllegalArgumentException("Invalid warmup duration");
        if (warmups < 0 || measurements < 1) throw new IllegalArgumentException("Invalid iterations");
        JenaSystem.init();
        Lang lang = RDFLanguages.nameToLang(args[1]);
        if (lang == null) throw new IllegalArgumentException("Unknown syntax: " + args[1]);
        byte[] data = Files.readAllBytes(path);
        String base = path.toUri().toString();
        Counter counter = new Counter();
        // Untimed validation/counting parse; counts parser events, not unique stored triples.
        parse(data, lang, base, counter);
        StreamRDFBase sink = new StreamRDFBase();
        System.out.println("phase,iteration,elapsed_ns,triples,quads");
        // Buffer durations: console/CSV output must not delay the warmup loop.
        java.util.List<Long> warmupTimes = new java.util.ArrayList<>();
        long warmupBudget = (long)(warmupSeconds * 1_000_000_000L);
        long accumulatedParseTime = 0;
        while (warmupTimes.size() < warmups || accumulatedParseTime < warmupBudget) {
            long start = System.nanoTime();
            parse(data, lang, base, sink);
            long elapsed = System.nanoTime() - start;
            warmupTimes.add(elapsed);
            accumulatedParseTime += elapsed;
        }
        long[] measuredTimes = new long[measurements];
        for (int i = 0; i < measurements; i++) {
            long start = System.nanoTime();
            parse(data, lang, base, sink);
            measuredTimes[i] = System.nanoTime() - start;
        }
        for (int i = 0; i < warmupTimes.size(); i++) {
            System.out.println("warmup," + (i + 1) + "," + warmupTimes.get(i)
                + "," + counter.triples + "," + counter.quads);
        }
        for (int i = 0; i < measurements; i++) {
            System.out.println("measurement," + (i + 1) + "," + measuredTimes[i]
                + "," + counter.triples + "," + counter.quads);
        }
    }
}

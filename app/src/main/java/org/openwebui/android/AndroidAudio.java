package org.openwebui.android;

import android.media.MediaCodec;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.media.MediaMuxer;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.nio.ByteBuffer;
import java.util.function.Function;

/**
 * P130 — découpage audio local par les API Android (MediaExtractor /
 * MediaMuxer), sans transcodage : les trames compressées d'origine sont
 * réécrites dans des conteneurs m4a (AAC/AMR) ou webm (Opus/Vorbis).
 *
 * Utilisé par `split_audio()` (routers/audio) via le pont Python
 * (`audio_bridge`, enregistré par `android_main.register_audio_split`) pour
 * les fichiers de plus de 20 Mo dont le format n'est pas couvert par le
 * découpage pur Python (wav/mp3).
 *
 * Entrée : JSON {"path": "...", "max_bytes": N}
 * Sortie : JSON ["chunk0.m4a", ...] ou ["ERROR: ..."]
 */
public class AndroidAudio implements Function<String, String> {

    @Override
    public String apply(String spec) {
        try {
            JSONObject o = new JSONObject(spec);
            JSONArray out = split(o.getString("path"), (long) o.getDouble("max_bytes"));
            return out.toString();
        } catch (Exception e) {
            JSONArray err = new JSONArray();
            err.put("ERROR: " + e);
            return err.toString();
        }
    }

    /** Découpe `path` en morceaux d'au plus `max_bytes` octets (approx.). */
    public JSONArray split(String path, long maxBytes) throws Exception {
        JSONArray out = new JSONArray();
        MediaExtractor extractor = new MediaExtractor();
        extractor.setDataSource(path);
        try {
            int trackIndex = -1;
            MediaFormat format = null;
            for (int i = 0; i < extractor.getTrackCount(); i++) {
                MediaFormat f = extractor.getTrackFormat(i);
                String mime = f.getString(MediaFormat.KEY_MIME);
                if (mime != null && mime.startsWith("audio/")) {
                    trackIndex = i;
                    format = f;
                    break;
                }
            }
            if (trackIndex < 0 || format == null) {
                throw new IllegalArgumentException("aucune piste audio dans " + path);
            }
            extractor.selectTrack(trackIndex);

            String mime = format.getString(MediaFormat.KEY_MIME);
            boolean webm = mime != null && mime.contains("webm");
            String outExt = webm ? ".webm" : ".m4a";
            int muxerFormat = webm
                    ? MediaMuxer.OutputFormat.MUXER_OUTPUT_WEBM
                    : MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4;

            File src = new File(path);
            long srcLen = src.length();
            long durationUs = format.containsKey(MediaFormat.KEY_DURATION)
                    ? format.getLong(MediaFormat.KEY_DURATION) : 0L;
            // durée visée par morceau : proportionnelle à max_bytes, marge 10 %
            long chunkUs = durationUs > 0 && srcLen > 0
                    ? (long) (durationUs * ((maxBytes * 0.9) / (double) srcLen))
                    : 60_000_000L;
            if (chunkUs < 10_000_000L) {
                chunkUs = 10_000_000L;
            }
            long maxBytesChunk = (long) (maxBytes * 0.9);

            String base = path.substring(0, path.lastIndexOf('.'));
            MediaMuxer muxer = null;
            int outTrack = -1;
            int index = 0;
            long chunkStartUs = 0L;
            long written = 0L;
            ByteBuffer buf = ByteBuffer.allocate(2 * 1024 * 1024);
            MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();

            while (true) {
                int size = extractor.readSampleData(buf, 0);
                if (size < 0) {
                    break;
                }
                long pts = extractor.getSampleTime();
                if (muxer == null) {
                    String chunkPath = base + "_chunk_" + index + outExt;
                    muxer = new MediaMuxer(chunkPath, muxerFormat);
                    outTrack = muxer.addTrack(format);
                    muxer.start();
                    out.put(chunkPath);
                    chunkStartUs = pts;
                    written = 0L;
                }
                buf.position(0);
                buf.limit(size);
                info.offset = 0;
                info.size = size;
                info.presentationTimeUs = pts - chunkStartUs;
                info.flags = extractor.getSampleFlags();
                muxer.writeSampleData(outTrack, buf, info);
                written += size;

                boolean cut = (pts - chunkStartUs) >= chunkUs || written >= maxBytesChunk;
                boolean last = !extractor.advance();
                if (cut && !last) {
                    muxer.stop();
                    muxer.release();
                    muxer = null;
                    index++;
                }
                if (last) {
                    break;
                }
            }
            if (muxer != null) {
                muxer.stop();
                muxer.release();
            }
            return out;
        } finally {
            extractor.release();
        }
    }
}

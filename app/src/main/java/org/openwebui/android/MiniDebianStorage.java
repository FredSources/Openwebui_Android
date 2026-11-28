package org.openwebui.android;

import android.content.Context;

import java.io.File;
import java.io.FileWriter;

/**
 * P173 — emplacement unique du « storage » du mini-Debian.
 *
 * Les binaires et le rootfs restent dans getFilesDir() (volume interne, seul
 * utilisable pour l'exécution). Les DONNÉES restent ici, dans
 * getExternalFilesDir(null)/minidebian/storage : ce chemin est à la fois
 * monté dans le conteneur en /root/storage et exposé au navigateur de
 * fichiers via {@link MiniDebianDocumentsProvider} (Storage Access Framework),
 * exactement comme Termux expose son $HOME.
 */
public final class MiniDebianStorage {

    private MiniDebianStorage() {
    }

    public static File get(Context context) {
        File externe = null;
        try {
            externe = context.getExternalFilesDir(null);
        } catch (Exception ignore) {
            // repli sur la mémoire interne si le volume externe est indisponible
        }
        File home = (externe != null) ? externe : context.getFilesDir();
        File storage = new File(new File(home, "minidebian"), "storage");
        storage.mkdirs();
        new File(storage, "work").mkdirs();

        File notice = new File(storage, "LISEZ-MOI.txt");
        if (!notice.exists()) {
            try (FileWriter writer = new FileWriter(notice)) {
                writer.write("Stockage du mini-Debian OpenWebUI Android\n"
                        + "\n"
                        + "Ce dossier est exposé dans le navigateur de fichiers via\n"
                        + "OpenWebUI Android > Mini Debian (Storage Access Framework).\n"
                        + "Dans le shell root, il est monté en /root/storage.\n"
                        + "Les fichiers déposés ici sont visibles des deux côtés.\n"
                        + "\n"
                        + "Binaires et rootfs (non modifiables ici) :\n"
                        + new File(context.getFilesDir(), "minidebian").getAbsolutePath() + "\n");
            } catch (Exception ignore) {
                // le storage reste utilisable même si la notice ne peut pas être écrite
            }
        }
        return storage;
    }
}

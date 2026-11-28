package org.openwebui.android;

import android.content.res.AssetFileDescriptor;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.graphics.Point;
import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract.Document;
import android.provider.DocumentsContract.Root;
import android.provider.DocumentsProvider;
import android.webkit.MimeTypeMap;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.Collections;
import java.util.LinkedList;

/**
 * P173 — fournisseur SAF exposant le storage du mini-Debian aux navigateurs
 * de fichiers, comme TermuxDocumentsProvider expose $HOME pour Termux.
 *
 * Le root est `getExternalFilesDir(null)/minidebian/storage`, le même dossier
 * que celui monté en /root/storage dans le conteneur. Il n'y a donc aucun
 * chemin à traduire depuis une URI SAF : le fournisseur sert directement des
 * fichiers réels, et Python utilise le même chemin via OPENWEBUI_ANDROID_STORAGE.
 */
public class MiniDebianDocumentsProvider extends DocumentsProvider {

    private static final String ALL_MIME_TYPES = "*/*";

    private static final String[] DEFAULT_ROOT_PROJECTION = new String[]{
            Root.COLUMN_ROOT_ID,
            Root.COLUMN_MIME_TYPES,
            Root.COLUMN_FLAGS,
            Root.COLUMN_ICON,
            Root.COLUMN_TITLE,
            Root.COLUMN_SUMMARY,
            Root.COLUMN_DOCUMENT_ID,
            Root.COLUMN_AVAILABLE_BYTES
    };

    private static final String[] DEFAULT_DOCUMENT_PROJECTION = new String[]{
            Document.COLUMN_DOCUMENT_ID,
            Document.COLUMN_MIME_TYPE,
            Document.COLUMN_DISPLAY_NAME,
            Document.COLUMN_LAST_MODIFIED,
            Document.COLUMN_FLAGS,
            Document.COLUMN_SIZE
    };

    @Override
    public boolean onCreate() {
        return true;
    }

    private File baseDir() throws FileNotFoundException {
        if (getContext() == null) {
            throw new FileNotFoundException("contexte indisponible");
        }
        return MiniDebianStorage.get(getContext());
    }

    @Override
    public Cursor queryRoots(String[] projection) {
        MatrixCursor result = new MatrixCursor(
                projection != null ? projection : DEFAULT_ROOT_PROJECTION);
        try {
            File base = baseDir();
            MatrixCursor.RowBuilder row = result.newRow();
            row.add(Root.COLUMN_ROOT_ID, base.getAbsolutePath());
            row.add(Root.COLUMN_DOCUMENT_ID, base.getAbsolutePath());
            row.add(Root.COLUMN_TITLE, "Mini Debian (OpenWebUI)");
            row.add(Root.COLUMN_SUMMARY, "Stockage du shell root");
            row.add(Root.COLUMN_MIME_TYPES, ALL_MIME_TYPES);
            row.add(Root.COLUMN_FLAGS,
                    Root.FLAG_SUPPORTS_CREATE | Root.FLAG_SUPPORTS_SEARCH
                            | Root.FLAG_SUPPORTS_IS_CHILD);
            row.add(Root.COLUMN_AVAILABLE_BYTES, base.getFreeSpace());
            row.add(Root.COLUMN_ICON, R.mipmap.ic_launcher);
        } catch (FileNotFoundException ignore) {
            // aucun root tant que le stockage n'est pas disponible
        }
        return result;
    }

    @Override
    public Cursor queryDocument(String documentId, String[] projection)
            throws FileNotFoundException {
        MatrixCursor result = new MatrixCursor(
                projection != null ? projection : DEFAULT_DOCUMENT_PROJECTION);
        includeFile(result, documentId, null);
        return result;
    }

    @Override
    public Cursor queryChildDocuments(String parentDocumentId, String[] projection,
                                      String sortOrder) throws FileNotFoundException {
        MatrixCursor result = new MatrixCursor(
                projection != null ? projection : DEFAULT_DOCUMENT_PROJECTION);
        File parent = getFileForDocId(parentDocumentId);
        File[] children = parent.listFiles();
        if (children != null) {
            for (File child : children) {
                includeFile(result, null, child);
            }
        }
        return result;
    }

    @Override
    public ParcelFileDescriptor openDocument(String documentId, String mode,
                                             CancellationSignal signal)
            throws FileNotFoundException {
        File file = getFileForDocId(documentId);
        return ParcelFileDescriptor.open(file, ParcelFileDescriptor.parseMode(mode));
    }

    @Override
    public AssetFileDescriptor openDocumentThumbnail(String documentId, Point sizeHint,
                                                     CancellationSignal signal)
            throws FileNotFoundException {
        File file = getFileForDocId(documentId);
        ParcelFileDescriptor pfd = ParcelFileDescriptor.open(
                file, ParcelFileDescriptor.MODE_READ_ONLY);
        return new AssetFileDescriptor(pfd, 0, file.length());
    }

    @Override
    public String createDocument(String parentDocumentId, String mimeType, String displayName)
            throws FileNotFoundException {
        File parent = getFileForDocId(parentDocumentId);
        if (!parent.isDirectory()) {
            throw new FileNotFoundException(parentDocumentId + " n'est pas un dossier");
        }
        File created = new File(parent, displayName);
        int suffix = 2;
        while (created.exists()) {
            created = new File(parent, displayName + " (" + suffix++ + ")");
        }
        try {
            boolean ok = Document.MIME_TYPE_DIR.equals(mimeType)
                    ? created.mkdir() : created.createNewFile();
            if (!ok) {
                throw new FileNotFoundException("création impossible : " + created);
            }
        } catch (IOException e) {
            throw new FileNotFoundException("création impossible : " + created);
        }
        return created.getAbsolutePath();
    }

    @Override
    public void deleteDocument(String documentId) throws FileNotFoundException {
        File file = getFileForDocId(documentId);
        if (file.equals(baseDir())) {
            throw new FileNotFoundException("racine du storage non supprimable");
        }
        if (!file.delete()) {
            throw new FileNotFoundException("suppression impossible : " + documentId);
        }
    }

    @Override
    public String getDocumentType(String documentId) throws FileNotFoundException {
        return mimeTypeOf(getFileForDocId(documentId));
    }

    @Override
    public Cursor querySearchDocuments(String rootId, String query, String[] projection)
            throws FileNotFoundException {
        MatrixCursor result = new MatrixCursor(
                projection != null ? projection : DEFAULT_DOCUMENT_PROJECTION);
        File parent = getFileForDocId(rootId);
        LinkedList<File> pending = new LinkedList<>();
        pending.add(parent);
        String needle = query == null ? "" : query.toLowerCase();
        while (!pending.isEmpty() && result.getCount() < 50) {
            File file = pending.removeFirst();
            if (file.isDirectory()) {
                File[] children = file.listFiles();
                if (children != null) {
                    Collections.addAll(pending, children);
                }
            } else if (file.getName().toLowerCase().contains(needle)) {
                includeFile(result, null, file);
            }
        }
        return result;
    }

    @Override
    public boolean isChildDocument(String parentDocumentId, String documentId) {
        try {
            File parent = getFileForDocId(parentDocumentId);
            File child = getFileForDocId(documentId);
            return !child.equals(parent) && isInside(child, parent);
        } catch (FileNotFoundException e) {
            return false;
        }
    }

    private File getFileForDocId(String docId) throws FileNotFoundException {
        if (docId == null) {
            throw new FileNotFoundException("identifiant null");
        }
        File base = baseDir();
        File file = new File(docId);
        if (!isInside(file, base)) {
            throw new FileNotFoundException("hors du storage : " + docId);
        }
        if (!file.exists()) {
            throw new FileNotFoundException(docId + " introuvable");
        }
        return file;
    }

    private static boolean isInside(File file, File parent) throws FileNotFoundException {
        try {
            String chemin = file.getCanonicalPath();
            String racine = parent.getCanonicalPath();
            return chemin.equals(racine) || chemin.startsWith(racine + File.separator);
        } catch (IOException e) {
            throw new FileNotFoundException(e.getMessage());
        }
    }

    private static String mimeTypeOf(File file) {
        if (file.isDirectory()) {
            return Document.MIME_TYPE_DIR;
        }
        String name = file.getName();
        int dot = name.lastIndexOf('.');
        if (dot >= 0) {
            String mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(
                    name.substring(dot + 1).toLowerCase());
            if (mime != null) {
                return mime;
            }
        }
        return "application/octet-stream";
    }

    private void includeFile(MatrixCursor result, String docId, File file)
            throws FileNotFoundException {
        if (docId == null) {
            docId = file.getAbsolutePath();
        } else {
            file = new File(docId);
        }
        File resolved = getFileForDocId(docId);
        String mime = mimeTypeOf(resolved);
        int flags = 0;
        if (resolved.isDirectory()) {
            if (resolved.canWrite()) {
                flags |= Document.FLAG_DIR_SUPPORTS_CREATE;
            }
        } else if (resolved.canWrite()) {
            flags |= Document.FLAG_SUPPORTS_WRITE;
        }
        File parent = resolved.getParentFile();
        if (parent != null && parent.canWrite()) {
            flags |= Document.FLAG_SUPPORTS_DELETE;
        }
        if (mime.startsWith("image/")) {
            flags |= Document.FLAG_SUPPORTS_THUMBNAIL;
        }
        MatrixCursor.RowBuilder row = result.newRow();
        row.add(Document.COLUMN_DOCUMENT_ID, docId);
        row.add(Document.COLUMN_DISPLAY_NAME, resolved.getName());
        row.add(Document.COLUMN_SIZE, resolved.length());
        row.add(Document.COLUMN_MIME_TYPE, mime);
        row.add(Document.COLUMN_LAST_MODIFIED, resolved.lastModified());
        row.add(Document.COLUMN_FLAGS, flags);
    }
}

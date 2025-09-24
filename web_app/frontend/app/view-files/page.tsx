"use client"

import React, { useEffect, useState } from "react";
import { apiFetch } from "../services/api";
import { performLogout } from "../services/logout";
import FileTable from "./file_table";
import FileActions from "./file_actions";

export interface FileItem {
  id: number;
  database: string;
  file: string;
}

// Helper to download file with correct extension
function downloadFile(f: FileItem) {
  return async (e: React.MouseEvent) => {
    e.preventDefault();
    document.body.style.cursor = "wait";
    try {
      // Use apiFetch which will attempt refresh
      const resText = await apiFetch(`/api/core/files/${f.id}/download/`, { method: "GET" });
      // If apiFetch returned undefined it already handled logout/redirect -> stop
      if (typeof resText === "undefined") return;
      // apiFetch returns string for non-json responses (our FileResponse returns bytes);
      // if it's a string we can create a blob
      const blob = new Blob([resText], { type: "application/octet-stream" });

      // Preserve original extension (.sqlite, .sqlite3, .sqlite6, etc.)
      const fileUrl = f.file || "";
      const extMatch = fileUrl.match(/\.(sqlite\d*|db)$/i);
      const ext = extMatch ? extMatch[0] : ".sqlite";
      const link = document.createElement("a");
      link.href = window.URL.createObjectURL(blob);
      link.download = `${f.database}${ext}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(link.href);
    } catch (err: any) {
      const msg = err?.message || String(err);
      // apiFetch already tries refresh and will perform logout when appropriate.
      // Here just surface the error to the user.
      alert(msg);
      return;
    } finally {
      document.body.style.cursor = "default";
    }
  };
}

const ViewFilesPage: React.FC = () => {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc');
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [refreshLoading, setRefreshLoading] = useState(false);
  const [clearLoading, setClearLoading] = useState(false);
  const [addLoading, setAddLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchFiles = async () => {
    setLoading(true);
    setError(null);
    console.log("fetchFiles: start");
    try {
      const data = await apiFetch("/api/core/files/");
      if (typeof data === "undefined") return; // apiFetch handled logout/redirect
      console.log("fetchFiles: success", data);
      // Sort according to selected order (desc = newest first)
      const sorted = Array.isArray(data)
        ? data.sort((a, b) => (sortOrder === 'desc' ? b.id - a.id : a.id - b.id))
        : [];
      setFiles(sorted);
      setSelected([]); // Clear selection whenever files are refreshed
    } catch (e: any) {
      console.error("fetchFiles: error", e);
      const msg = e.message || JSON.stringify(e);
      // Let apiFetch handle auth-related redirects; show other errors
      alert(msg);
    } finally {
      setLoading(false);
      console.log("fetchFiles: end");
    }
  };

  useEffect(() => {
  console.log("useEffect: fetchFiles");
  fetchFiles();
  }, []);

  // When sort order changes, re-sort already-fetched files in-place so the UI updates
  useEffect(() => {
    setFiles(prev => [...prev].sort((a, b) => (sortOrder === 'desc' ? b.id - a.id : a.id - b.id)));
  }, [sortOrder]);

  const handleDelete = async () => {
    setDeleteLoading(true);
    document.body.style.cursor = "wait";
    console.log("Delete button: start", selected);
    try {
      for (const id of selected) {
        try {
          console.log("Delete button: deleting", id);
          const delRes = await apiFetch(`/api/core/files/${id}/`, { method: "DELETE" });
          if (typeof delRes === "undefined") return; // apiFetch handled logout/redirect
          console.log("Delete button: deleted", id);
        } catch (e: any) {
          console.error("Delete button: error", id, e);
          const msg = e.message || JSON.stringify(e);
          // Let apiFetch handle auth failures; otherwise show error
          alert(msg);
          return;
        }
      }
      setSelected([]);
      console.log("Delete button: fetchFiles");
      await fetchFiles();
    } finally {
      setDeleteLoading(false);
      document.body.style.cursor = "default";
      console.log("Delete button: end");
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <h1 className="text-2xl font-bold mb-6">Database Files</h1>
      {/* Order control moved to top as requested */}
      <div className="flex items-center gap-3 mb-4">
        <label className="text-sm font-medium">Order:</label>
        <select
          value={sortOrder}
          onChange={e => setSortOrder(e.target.value as 'desc' | 'asc')}
          className="px-2 py-1 rounded border"
          title="Sort files by ID"
        >
          <option value="desc">Newest first</option>
          <option value="asc">Oldest first</option>
        </select>
      </div>
      {/* Action buttons moved above the table */}
      <FileActions
        selected={selected}
        deleteLoading={deleteLoading}
        refreshLoading={refreshLoading}
        clearLoading={clearLoading}
        addLoading={addLoading}
        handleDelete={handleDelete}
        fetchFiles={fetchFiles}
        setRefreshLoading={setRefreshLoading}
        setClearLoading={setClearLoading}
        setAddLoading={setAddLoading}
        apiFetch={apiFetch}
      />
      {loading && <div className="mb-4 text-gray-500">Loading...</div>}
  {/* error popup only, no HTML error rendering */}
      {files.length === 0 ? (
        <div className="text-gray-400">No databases found.</div>
      ) : (
        <FileTable
          files={files}
          selected={selected}
          setSelected={setSelected}
          downloadFile={downloadFile}
        />
      )}
    </div>
  );
};

export default ViewFilesPage;
